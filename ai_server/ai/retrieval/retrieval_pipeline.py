import logging
import time

from ai.config import (
    QDRANT_COLLECTION,
    RERANKER_ENABLED,
    RETRIEVAL_SCORE_THRESHOLD,
    RETRIEVAL_TOP_K_POST_RERANK,
    RETRIEVAL_TOP_K_PRE_RERANK,
)
from ai.retrieval.qdrant_searcher import search_collection
from ai.retrieval.query_embedder import bm25_embed_query, embed_query
from ai.retrieval.reranker import rerank_chunks
from ai.retrieval.result_models import RetrievalResult

logger = logging.getLogger("knowledge_hub.retrieval.pipeline")


def retrieve(
    query: str,
    category_filter: list[str] | None = None,
    access_level: str | None = None,
    top_k: int | None = None,
    score_threshold: float | None = None,
    # Legacy positional compat — old callers pass collection as 2nd arg
    collection: str | None = None,  # noqa: ARG001 — ignored, always uses QDRANT_COLLECTION
) -> RetrievalResult:
    """Embed a query, search Qdrant, and return ranked chunks.

    Searches QDRANT_COLLECTION ("documents") — the single universal collection.
    Pass ``category_filter`` to restrict to specific document categories
    (e.g. ["sop", "legal"]). Pass None to search the full corpus.

    No LLM is called here. No intent classification. No reformulation.
    This function receives a clean query string and returns chunks.
    """
    start = time.perf_counter()

    resolved_top_k    = top_k          if top_k          is not None else RETRIEVAL_TOP_K_PRE_RERANK
    resolved_threshold = score_threshold if score_threshold is not None else RETRIEVAL_SCORE_THRESHOLD

    query_vector = embed_query(query)

    # BM25 sparse vector — None when HYBRID_SEARCH_ENABLED=false or model unavailable.
    # qdrant_searcher falls back to dense-only when this is None.
    sparse_query_vector = bm25_embed_query(query)

    chunks, below_threshold_count = search_collection(
        query_vector=query_vector,
        collection=QDRANT_COLLECTION,
        top_k=resolved_top_k,
        score_threshold=resolved_threshold,
        access_level_filter=access_level,
        category_filter=category_filter,
        sparse_query_vector=sparse_query_vector,
    )
    if RERANKER_ENABLED and chunks:
        chunks = rerank_chunks(query, chunks, top_k=RETRIEVAL_TOP_K_POST_RERANK)
    else:
        # Keep retrieval outputs bounded even when reranking is disabled.
        chunks = chunks[:RETRIEVAL_TOP_K_POST_RERANK]

    # Use rerank_score as the confidence signal when the reranker ran.
    # bge-reranker-v2-gemma outputs sigmoid-normalized scores in [0.0, 1.0] —
    # the same scale as cosine similarity — so existing confidence thresholds
    # remain valid. rerank_score is a better relevance signal than vector/RRF
    # score and is independent of whether hybrid or dense retrieval was used.
    if RERANKER_ENABLED and chunks and chunks[0].rerank_score is not None:
        top_score = chunks[0].rerank_score
    else:
        top_score = chunks[0].score if chunks else 0.0

    score_distribution = [c.score for c in chunks]

    latency_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "[RetrievalPipeline] query=%r collection=%s category_filter=%s "
        "chunks=%d top_score=%.4f latency=%.0fms",
        query[:80],
        QDRANT_COLLECTION,
        category_filter,
        len(chunks),
        top_score,
        latency_ms,
    )

    return RetrievalResult(
        query_text=query,
        collection_searched=QDRANT_COLLECTION,
        chunks=chunks,
        top_score=top_score,
        score_distribution=score_distribution,
        threshold_applied=resolved_threshold,
        empty=len(chunks) == 0,
        below_threshold_count=below_threshold_count,
        latency_ms=latency_ms,
    )
