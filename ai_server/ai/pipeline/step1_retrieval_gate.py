"""Step 1 — Retrieval Gate.

Coordinates Group 1 routing with the Qdrant retrieval layer.
Returns a RetrievalResult that downstream stages consume without
knowing whether retrieval ran, was refused, or was skipped.

Architecture: all documents live in a single QDRANT_COLLECTION ("documents").
Category-scoped queries are handled via Qdrant payload filters, not separate
collections. Pass a list of category strings as ``requested_collection`` to
narrow retrieval; pass None (or omit) to search the full corpus.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ai.agents.models.session import SessionContext
from ai.agents.orchestrator import run_group1, Group1Result
from ai.agents.models.retrieval_plan import PlannerRetrievalQuery
from ai.config import (
    RERANKER_ENABLED,
    QDRANT_COLLECTION,
    RETRIEVAL_SCORE_THRESHOLD,
    RETRIEVAL_TOP_K_POST_RERANK,
    RETRIEVAL_TOP_K_PRE_RERANK,
)
from ai.retrieval.qdrant_searcher import search_collection
from ai.retrieval.query_embedder import bm25_embed_query, embed_query
from ai.retrieval.reranker import rerank_chunks

logger = logging.getLogger("knowledge_hub.pipeline.step1")


@dataclass
class RetrievalResult:
    query_used: str              # the query that was actually embedded
    chunks: list                 # the raw chunk objects from the retrieval layer
    top_score: float             # confidence score of the first/best chunk (0.0 if none)
    chunk_count: int             # how many chunks returned
    was_refused: bool            # True if Group1 said should_refuse
    refusal_message: str | None  # populated if was_refused
    was_retrieved: bool          # True if retrieval actually ran
    group1_result: Group1Result  # the full Group1Result, passed through
    latency_ms: float            # total time for this function in ms
    collections_searched: list[str] = field(default_factory=list)
    planner_used: bool = False
    subquery_matches: dict[str, list[str]] = field(default_factory=dict)


def _resolve_category_filter(
    requested: str | list[str] | None,
) -> list[str] | None:
    """Normalise the incoming collection/category parameter into a filter list.

    Returns a deduplicated list of lowercase category strings, or None to
    search without any category restriction (full corpus).

    Accepts:
    - None              → no filter, search everything
    - ""                → no filter
    - "default"         → no filter (legacy sentinel)
    - "sop"             → filter to category == "sop"
    - ["sop", "legal"]  → filter to category IN ["sop", "legal"]
    """
    if requested is None:
        return None

    # Single-string path
    if isinstance(requested, str):
        cleaned = requested.strip().lower()
        if not cleaned or cleaned == "default":
            return None
        return [cleaned]

    # List path — defensive against nested structures from callers
    normalized: list[str] = []
    for item in requested:
        if isinstance(item, (list, tuple, set)):
            candidates = list(item)
        else:
            candidates = [item]
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            cleaned = candidate.strip().lower()
            if cleaned and cleaned != "default":
                normalized.append(cleaned)

    if not normalized:
        return None

    # Preserve order, deduplicate
    return list(dict.fromkeys(normalized))


def _empty_result(
    query_used: str,
    group1_result: Group1Result,
    start: float,
    *,
    was_refused: bool = False,
    refusal_message: str | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        query_used=query_used,
        chunks=[],
        top_score=0.0,
        chunk_count=0,
        was_refused=was_refused,
        refusal_message=refusal_message,
        was_retrieved=False,
        group1_result=group1_result,
        collections_searched=[],
        planner_used=False,
        subquery_matches={},
        latency_ms=(time.perf_counter() - start) * 1000,
    )


def _score_for_rank(chunk: object) -> float:
    rerank_score = getattr(chunk, "rerank_score", None)
    if rerank_score is not None:
        try:
            return float(rerank_score)
        except (TypeError, ValueError):
            pass
    try:
        return float(getattr(chunk, "score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _chunk_key(chunk: object, fallback_index: int) -> str:
    for attr_name in ("chunk_id", "id"):
        value = getattr(chunk, attr_name, None)
        if value:
            return str(value)
    return f"chunk_index:{fallback_index}"


def _search_for_query(
    *,
    query_text: str,
    category_filter: list[str] | None,
) -> list:
    """Run the existing dense/BM25 retrieval path for one retrieval query."""
    query_vector = embed_query(query_text)
    sparse_query_vector = bm25_embed_query(query_text)

    chunks, _ = search_collection(
        query_vector=query_vector,
        collection=QDRANT_COLLECTION,
        top_k=RETRIEVAL_TOP_K_PRE_RERANK,
        score_threshold=RETRIEVAL_SCORE_THRESHOLD,
        category_filter=category_filter,
        sparse_query_vector=sparse_query_vector,
    )

    # Dense-only search returns score-ranked points but keep this defensive sort.
    # Hybrid RRF results are already ranked by Qdrant.
    if sparse_query_vector is None:
        chunks = sorted(chunks, key=lambda c: c.score, reverse=True)

    if RERANKER_ENABLED and chunks:
        chunks = rerank_chunks(
            query_text,
            chunks[:RETRIEVAL_TOP_K_PRE_RERANK],
            top_k=RETRIEVAL_TOP_K_POST_RERANK,
        )
    else:
        # Keep the final per-subquery budget stable even when the cross-encoder
        # reranker is disabled. In that mode Qdrant/RRF order is the final rank.
        chunks = chunks[:RETRIEVAL_TOP_K_POST_RERANK]

    return chunks


def _search_one_subquery(
    planner_query: PlannerRetrievalQuery,
    category_filter: list[str] | None,
) -> tuple[str, list]:
    """Run retrieval for a single planner subquery. Returns (query_id, chunks).

    All exceptions are caught here so a failed subquery does not cancel the
    others when called from a ThreadPoolExecutor.
    """
    try:
        chunks = _search_for_query(
            query_text=planner_query.query,
            category_filter=category_filter,
        )
        logger.info(
            "[Step1] Subquery retrieved: id=%s query=%r chunks=%d",
            planner_query.id,
            planner_query.query[:80],
            len(chunks),
        )
        return planner_query.id, chunks
    except Exception as subquery_exc:
        logger.warning(
            "[Step1] Subquery failed: id=%s query=%r error=%s",
            planner_query.id,
            planner_query.query[:80],
            subquery_exc,
        )
        return planner_query.id, []


def _planner_queries_or_fallback(group1_result: Group1Result) -> list[PlannerRetrievalQuery]:
    plan = group1_result.retrieval_plan
    if plan and plan.retrieval_queries:
        return plan.retrieval_queries
    return [
        PlannerRetrievalQuery(
            id="q1",
            task_ids=["task_1"],
            query=group1_result.query_for_retrieval,
            priority="high",
        )
    ]


def _merge_subquery_chunks(
    subquery_results: list[tuple[str, list]],
) -> tuple[list, dict[str, list[str]]]:
    best_by_key: dict[str, object] = {}
    best_score_by_key: dict[str, float] = {}
    matches: dict[str, list[str]] = {}

    for query_id, chunks in subquery_results:
        for index, chunk in enumerate(chunks):
            key = _chunk_key(chunk, index)
            score = _score_for_rank(chunk)
            matches.setdefault(key, [])
            if query_id not in matches[key]:
                matches[key].append(query_id)
            if key not in best_by_key or score > best_score_by_key[key]:
                best_by_key[key] = chunk
                best_score_by_key[key] = score

    merged = sorted(
        best_by_key.values(),
        key=_score_for_rank,
        reverse=True,
    )
    return merged, matches


def run_retrieval_gate(
    query: str,
    session: SessionContext,
    requested_collection: str | list[str] | None = None,
) -> RetrievalResult:
    """Run Group 1 routing then conditionally call the retrieval layer.

    ``requested_collection`` is now interpreted as a **category filter**:
    - None / empty → search all documents in QDRANT_COLLECTION
    - "sop"        → filter to documents with payload.category == "sop"
    - ["sop","hr"] → filter to documents in any of those categories

    Stage 2b may decompose the final standalone query into multiple retrieval
    subqueries. Each subquery is searched against the single ``documents``
    collection with the same optional Qdrant payload filter.

    Logic:
      1. Run Group 1 — always.
      2. If should_refuse → return with was_refused=True, no retrieval.
      3. If not should_retrieve → answer_transform or citation_lookup path, no retrieval.
      4. Otherwise → plan subqueries, search each one, rerank, dedupe, merge.

    Always returns a valid RetrievalResult — never raises.
    """
    start = time.perf_counter()

    # 1. Run Group 1 routing
    group1_result = run_group1(query, session)

    # 2. Refuse path — out-of-domain or fast-rejected
    if group1_result.should_refuse:
        logger.info(
            "[Step1] Refused: query=%r reason=%r",
            query[:80],
            group1_result.refusal_message,
        )
        return _empty_result(
            group1_result.query_for_retrieval, group1_result, start,
            was_refused=True, refusal_message=group1_result.refusal_message,
        )

    # 3. No-retrieval path — answer_transform or citation_lookup, no LLM retrieval needed
    if not group1_result.should_retrieve:
        logger.info(
            "[Step1] Skipping retrieval (mode=%r): query=%r",
            group1_result.context_mode.mode,
            query[:80],
        )
        return _empty_result(group1_result.query_for_retrieval, group1_result, start)

    # 4. Retrieval path: run one normal retrieval pass per planner subquery.
    try:
        category_filter = _resolve_category_filter(requested_collection)

        planner_queries = _planner_queries_or_fallback(group1_result)
        planner_used = bool(
            group1_result.retrieval_plan
            and group1_result.retrieval_plan.planner_method == "llm"
        )

        with ThreadPoolExecutor(max_workers=len(planner_queries)) as executor:
            futures = [
                executor.submit(_search_one_subquery, pq, category_filter)
                for pq in planner_queries
            ]
            subquery_results: list[tuple[str, list]] = [f.result() for f in futures]

        chunks, subquery_matches = _merge_subquery_chunks(subquery_results)

        # If a planner path produced no usable chunks, fall back once to the
        # original standalone query so planner failures do not lower recall.
        if not chunks and planner_queries[0].query != group1_result.query_for_retrieval:
            fallback_chunks = _search_for_query(
                query_text=group1_result.query_for_retrieval,
                category_filter=category_filter,
            )
            chunks, subquery_matches = _merge_subquery_chunks([("q_fallback", fallback_chunks)])

        top_score = _score_for_rank(chunks[0]) if chunks else 0.0
        logger.info(
            "[Step1] Retrieved: query=%r collection=%s category_filter=%s "
            "subqueries=%d chunks=%d top_score=%.4f planner=%s latency=%.0fms",
            group1_result.query_for_retrieval[:80],
            QDRANT_COLLECTION,
            category_filter,
            len(planner_queries),
            len(chunks),
            top_score,
            planner_used,
            (time.perf_counter() - start) * 1000,
        )

        return RetrievalResult(
            query_used=group1_result.query_for_retrieval,
            chunks=chunks,
            top_score=top_score,
            chunk_count=len(chunks),
            was_refused=False,
            refusal_message=None,
            was_retrieved=True,
            group1_result=group1_result,
            collections_searched=[QDRANT_COLLECTION],
            planner_used=planner_used,
            subquery_matches=subquery_matches,
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    except Exception as exc:
        logger.error("[Step1] Retrieval failed for query=%r: %s", query[:80], exc)
        return _empty_result(group1_result.query_for_retrieval, group1_result, start)
