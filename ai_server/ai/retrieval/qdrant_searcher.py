import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    Prefetch,
    SparseVector,
)

from ai.config import QDRANT_URL
from ai.retrieval.result_models import RetrievedChunk

logger = logging.getLogger("knowledge_hub.retrieval.qdrant_searcher")

_qdrant_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Return the module-level singleton QdrantClient."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=QDRANT_URL)
    return _qdrant_client


def list_collections() -> list[str]:
    """Return collection names currently available in Qdrant."""
    client   = _get_client()
    response = client.get_collections()
    return [c.name for c in response.collections if getattr(c, "name", None)]


def search_collection(
    query_vector: list[float],
    collection: str,
    top_k: int,
    score_threshold: float,
    access_level_filter: str | None = None,
    category_filter: list[str] | None = None,
    sparse_query_vector=None,
) -> tuple[list[RetrievedChunk], int]:
    """Search a Qdrant collection with the embedded query vector.

    Returns (chunks_that_passed_threshold, count_rejected_below_threshold).

    When ``sparse_query_vector`` is provided (a fastembed SparseEmbedding),
    performs hybrid search using Qdrant native Prefetch + Reciprocal Rank
    Fusion (RRF). The dense Prefetch applies ``score_threshold`` as a garbage
    filter; the RRF result is unthresholded because RRF scores (0.01–0.06
    range) are not comparable to cosine similarities.

    When ``sparse_query_vector`` is None, falls back to the standard dense
    vector search path with ``score_threshold`` applied directly.

    Filters applied at the Qdrant level:
    - ``category_filter``: restrict to chunks whose payload.category is in the
      provided list. Pass None (or omit) to search the full corpus.
    - ``access_level_filter``: restrict to a specific access level string.

    Raises ValueError if the collection does not exist.
    """
    client = _get_client()

    # Build combined Qdrant filter
    must_conditions = []

    if category_filter:
        if len(category_filter) == 1:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category_filter[0]))
            )
        else:
            must_conditions.append(
                FieldCondition(key="category", match=MatchAny(any=category_filter))
            )

    if access_level_filter is not None:
        must_conditions.append(
            FieldCondition(key="access_level", match=MatchValue(value=access_level_filter))
        )

    query_filter = Filter(must=must_conditions) if must_conditions else None

    try:
        if sparse_query_vector is not None:
            chunks, below_threshold_count = _hybrid_search(
                client=client,
                collection=collection,
                dense_vector=query_vector,
                sparse_vector=sparse_query_vector,
                top_k=top_k,
                dense_score_threshold=score_threshold,
                query_filter=query_filter,
                category_filter=category_filter,
            )
        else:
            chunks, below_threshold_count = _dense_search(
                client=client,
                collection=collection,
                query_vector=query_vector,
                top_k=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter,
                category_filter=category_filter,
            )
    except Exception as exc:
        exc_str = str(exc)
        if "Not found" in exc_str or "doesn't exist" in exc_str or "not found" in exc_str.lower():
            raise ValueError(f"Collection '{collection}' not found in Qdrant") from exc
        raise

    return chunks, below_threshold_count


def _dense_search(
    client: QdrantClient,
    collection: str,
    query_vector: list[float],
    top_k: int,
    score_threshold: float,
    query_filter,
    category_filter,
) -> tuple[list[RetrievedChunk], int]:
    """Dense-only vector search path (legacy / HYBRID_SEARCH_ENABLED=false)."""
    passing_response = _query_dense_points(
        client=client,
        collection_name=collection,
        query=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
        query_filter=query_filter,
        with_payload=True,
    )
    passing_results = passing_response.points

    # Second call with no threshold to compute below_threshold_count
    all_response = _query_dense_points(
        client=client,
        collection_name=collection,
        query=query_vector,
        limit=top_k,
        score_threshold=0.0,
        query_filter=query_filter,
        with_payload=False,
    )
    all_results = all_response.points

    below_threshold_count = max(0, len(all_results) - len(passing_results))
    chunks = [_map_scored_point(point, collection) for point in passing_results]

    score_range = (
        f"{passing_results[-1].score:.4f}–{passing_results[0].score:.4f}"
        if passing_results
        else "none"
    )
    logger.info(
        "[QdrantSearcher] mode=dense | collection=%s | category_filter=%s | "
        "passed=%d | rejected=%d | score_range=%s",
        collection,
        category_filter,
        len(chunks),
        below_threshold_count,
        score_range,
    )

    return chunks, below_threshold_count


def _query_dense_points(
    client: QdrantClient,
    collection_name: str,
    query: list[float],
    limit: int,
    score_threshold: float,
    query_filter,
    with_payload: bool,
):
    """Run dense search against either legacy unnamed or hybrid named-vector schema."""
    try:
        return client.query_points(
            collection_name=collection_name,
            query=query,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=with_payload,
            with_vectors=False,
        )
    except Exception as exc:
        if not _looks_like_missing_vector_name_error(exc):
            raise

        logger.info(
            "[QdrantSearcher] Dense query retry using named vector 'dense' for collection=%s",
            collection_name,
        )
        return client.query_points(
            collection_name=collection_name,
            query=query,
            using="dense",
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=with_payload,
            with_vectors=False,
        )


def _looks_like_missing_vector_name_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "vector" not in message:
        return False
    return any(
        marker in message
        for marker in (
            "using",
            "name",
            "dense",
            "default",
            "not found",
            "not existing",
        )
    )


def _hybrid_search(
    client: QdrantClient,
    collection: str,
    dense_vector: list[float],
    sparse_vector,
    top_k: int,
    dense_score_threshold: float,
    query_filter,
    category_filter,
) -> tuple[list[RetrievedChunk], int]:
    """Hybrid dense + BM25 search via Qdrant native Prefetch + RRF.

    The dense Prefetch applies ``dense_score_threshold`` as a garbage filter.
    The BM25 Prefetch has no threshold — exact term matches should always be
    included regardless of TF-IDF score magnitude.
    The RRF result is not filtered by threshold; the reranker acts as the
    precision gate on the merged candidates.
    """
    response = client.query_points(
        collection_name=collection,
        prefetch=[
            Prefetch(
                query=dense_vector,
                using="dense",
                filter=query_filter,
                limit=top_k,
                score_threshold=dense_score_threshold,
            ),
            Prefetch(
                query=SparseVector(
                    indices=list(sparse_vector.indices),
                    values=list(sparse_vector.values),
                ),
                using="bm25",
                filter=query_filter,
                limit=top_k,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        score_threshold=0.0,    # RRF scores are not cosine — no threshold here
        query_filter=query_filter,
        with_payload=True,
        with_vectors=False,
    )

    results = response.points
    chunks = [_map_scored_point(point, collection) for point in results]

    # below_threshold_count is meaningless for RRF (no threshold applied to output)
    below_threshold_count = 0

    score_range = (
        f"{results[-1].score:.4f}–{results[0].score:.4f}"
        if results
        else "none"
    )
    logger.info(
        "[QdrantSearcher] mode=hybrid_rrf | collection=%s | category_filter=%s | "
        "returned=%d | rrf_score_range=%s",
        collection,
        category_filter,
        len(chunks),
        score_range,
    )

    return chunks, below_threshold_count


def _map_scored_point(point, collection: str) -> RetrievedChunk:
    """Map a Qdrant ScoredPoint to a RetrievedChunk.

    Field names match what qdrant_writer.py stored during ingestion:
      text       → chunk_text
      filename   → source_filename
      heading    → section_heading
      category   → category (from payload, not collection name)
    """
    payload = point.payload or {}
    return RetrievedChunk(
        chunk_id=str(point.id),
        chunk_text=payload.get("text", ""),
        score=point.score,
        doc_id=payload.get("doc_id", ""),
        source_filename=payload.get("filename", ""),
        category=payload.get("category", "general"),
        section_heading=payload.get("heading") or "",
        page_number=payload.get("page_number", None),
        access_level=payload.get("access_level", "internal"),
        extraction_method=payload.get("extraction_method", ""),
        upload_date=payload.get("upload_date", ""),
        language=payload.get("language", "en"),
        chunk_index=payload.get("chunk_index", 0),
    )
