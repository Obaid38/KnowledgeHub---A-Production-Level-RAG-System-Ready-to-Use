import logging
import time

import redis as redis_lib
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field, field_validator

from ai.agents.config.agent_config_loader import load_agents_config
from ai.agents.models.session import SessionContext
from ai.config import (
    QDRANT_COLLECTION,
    REDIS_URL,
    RERANKER_ENABLED,
    RETRIEVAL_SCORE_THRESHOLD,
    RETRIEVAL_TOP_K_POST_RERANK,
    RETRIEVAL_TOP_K_PRE_RERANK,
)
from ai.config.company_profile import load_company_profile
from ai.session.redis_session_store import load_session, save_session
from ai.pipeline.pipeline_runner import run_pipeline
from ai.retrieval.qdrant_searcher import search_collection
from ai.retrieval.query_embedder import embed_query
from ai.retrieval.reranker import rerank_chunks
from ai.retrieval.retrieval_pipeline import retrieve

logger = logging.getLogger("knowledge_hub.api.qa")

router = APIRouter()


# ---------------------------------------------------------------------------
# /retrieve — retrieval-only debug endpoint (no LLM)
# ---------------------------------------------------------------------------

class RetrieveRequest(BaseModel):
    query: str
    # ``category`` narrows retrieval to chunks with matching payload.category.
    # Omit (or leave blank) to search the full corpus.
    category: str | None = None
    access_level: str | None = None
    top_k: int | None = None
    score_threshold: float | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v

    @field_validator("category")
    @classmethod
    def normalise_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not cleaned or cleaned in {"string", "null", "none", "default"}:
            return None
        return cleaned

    @field_validator("access_level")
    @classmethod
    def normalize_access_level(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in {"string", "null", "none"}:
            return None
        allowed = {"public", "internal", "restricted", "confidential"}
        if lowered not in allowed:
            raise ValueError(f"access_level must be one of {sorted(allowed)}")
        return lowered

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v <= 0:
            return None
        return v

    @field_validator("score_threshold")
    @classmethod
    def validate_score_threshold(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if v < 0:
            raise ValueError("score_threshold must be >= 0")
        return v


class ChunkResponse(BaseModel):
    chunk_id: str
    score: float
    rerank_score: float | None = None
    source_filename: str
    section_heading: str
    page_number: int | None
    category: str
    access_level: str
    extraction_method: str
    chunk_index: int = 0
    chunk_text: str


class RetrieveResponse(BaseModel):
    query: str
    collection: str
    category_filter: list[str] | None
    result_count: int
    top_score: float
    threshold_applied: float
    empty: bool
    below_threshold_count: int
    latency_ms: float
    chunks: list[ChunkResponse]


def _chunk_response(c) -> ChunkResponse:
    return ChunkResponse(
        chunk_id=c.chunk_id,
        score=c.score,
        rerank_score=getattr(c, "rerank_score", None),
        source_filename=c.source_filename,
        section_heading=c.section_heading,
        page_number=c.page_number,
        category=c.category,
        access_level=c.access_level,
        extraction_method=c.extraction_method,
        chunk_index=getattr(c, "chunk_index", 0),
        chunk_text=c.chunk_text,
    )


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_chunks(body: RetrieveRequest) -> RetrieveResponse:
    """Embed a query, search Qdrant, and return raw ranked chunks.

    This is a retrieval-only debugging endpoint — no LLM involved.
    Optionally pass ``category`` to restrict to chunks of that category.
    """
    category_filter = [body.category] if body.category else None

    try:
        result = retrieve(
            query=body.query,
            category_filter=category_filter,
            access_level=body.access_level,
            top_k=body.top_k,
            score_threshold=body.score_threshold,
        )
    except RuntimeError as exc:
        logger.error("[QA] Embedding failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        logger.error("[QA] Qdrant error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[QA] Unexpected error during retrieval")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}") from exc

    chunks = [_chunk_response(c) for c in result.chunks]

    return RetrieveResponse(
        query=result.query_text,
        collection=result.collection_searched,
        category_filter=category_filter,
        result_count=len(chunks),
        top_score=result.top_score,
        threshold_applied=result.threshold_applied,
        empty=result.empty,
        below_threshold_count=result.below_threshold_count,
        latency_ms=result.latency_ms,
        chunks=chunks,
    )


# ---------------------------------------------------------------------------
# /retrieve-debug - retrieval-only debug endpoint with pre/post rerank chunks
# ---------------------------------------------------------------------------

class RetrieveDebugRequest(RetrieveRequest):
    category_filter: list[str] | None = None
    use_reranker: bool = True
    post_rerank_top_k: int | None = None

    @field_validator("category_filter")
    @classmethod
    def normalize_category_filter(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = [item.strip().lower() for item in v if item and item.strip()]
        cleaned = [c for c in cleaned if c not in {"string", "null", "none", "default"}]
        return cleaned or None

    @field_validator("post_rerank_top_k")
    @classmethod
    def validate_post_rerank_top_k(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v <= 0:
            return None
        return v

class RetrieveDebugResponse(BaseModel):
    query: str
    collection: str
    category_filter: list[str] | None
    initial_count: int
    reranked_count: int
    result_count: int
    top_score: float
    threshold_applied: float
    below_threshold_count: int
    latency_ms: float
    reranker_requested: bool
    reranker_enabled: bool
    reranked: bool
    reranker_status: str
    rerank_error: str | None = None
    initial_chunks: list[ChunkResponse]
    reranked_chunks: list[ChunkResponse]
    chunks: list[ChunkResponse]


@router.post("/retrieve-debug", response_model=RetrieveDebugResponse)
def retrieve_debug_chunks(body: RetrieveDebugRequest) -> RetrieveDebugResponse:
    """Return both vector candidates and reranked chunks from this API process."""
    start = time.perf_counter()
    category_filter = body.category_filter or ([body.category] if body.category else None)
    resolved_top_k = body.top_k or RETRIEVAL_TOP_K_PRE_RERANK
    resolved_post_rerank_top_k = body.post_rerank_top_k or RETRIEVAL_TOP_K_POST_RERANK
    resolved_threshold = (
        body.score_threshold
        if body.score_threshold is not None
        else RETRIEVAL_SCORE_THRESHOLD
    )

    try:
        query_vector = embed_query(body.query)
        chunks, below_threshold_count = search_collection(
            query_vector=query_vector,
            collection=QDRANT_COLLECTION,
            top_k=resolved_top_k,
            score_threshold=resolved_threshold,
            access_level_filter=body.access_level,
            category_filter=category_filter,
        )
    except RuntimeError as exc:
        logger.error("[QA] Debug embedding failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        logger.error("[QA] Debug Qdrant error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[QA] Unexpected error during debug retrieval")
        raise HTTPException(status_code=500, detail=f"Retrieval debug failed: {exc}") from exc

    initial_chunks = list(chunks)
    initial_chunks.sort(key=lambda c: c.score, reverse=True)
    initial_chunk_responses = [_chunk_response(c) for c in initial_chunks]

    reranked = False
    reranker_status = "not_requested"
    rerank_error = None
    reranked_chunks = []
    output_chunks = initial_chunks

    if body.use_reranker:
        if not RERANKER_ENABLED:
            reranker_status = "disabled_by_env"
        elif not initial_chunks:
            reranker_status = "no_chunks"
        else:
            try:
                reranked_chunks = rerank_chunks(
                    body.query,
                    initial_chunks,
                    top_k=resolved_post_rerank_top_k,
                )
                rerank_scores_attached = any(
                    getattr(c, "rerank_score", None) is not None
                    for c in reranked_chunks
                )
                returned_rerank_top_k = (
                    len(reranked_chunks) > 0
                    and len(reranked_chunks) <= resolved_post_rerank_top_k
                    and len(reranked_chunks) < len(initial_chunks)
                )
                reranked = rerank_scores_attached or returned_rerank_top_k
                if reranked:
                    output_chunks = reranked_chunks
                    reranker_status = "reranked"
                else:
                    reranker_status = "model_unavailable_or_failed_open"
            except Exception as exc:
                rerank_error = str(exc)
                reranker_status = "failed"
                logger.warning("[QA] Debug reranker failed: %s", exc)

    reranked_chunk_responses = [_chunk_response(c) for c in reranked_chunks] if reranked else []
    output_chunk_responses = reranked_chunk_responses if reranked else initial_chunk_responses
    latency_ms = (time.perf_counter() - start) * 1000

    return RetrieveDebugResponse(
        query=body.query,
        collection=QDRANT_COLLECTION,
        category_filter=category_filter,
        initial_count=len(initial_chunks),
        reranked_count=len(reranked_chunks) if reranked else 0,
        result_count=len(output_chunks),
        top_score=output_chunks[0].score if output_chunks else 0.0,
        threshold_applied=resolved_threshold,
        below_threshold_count=below_threshold_count,
        latency_ms=latency_ms,
        reranker_requested=body.use_reranker,
        reranker_enabled=RERANKER_ENABLED,
        reranked=reranked,
        reranker_status=reranker_status,
        rerank_error=rerank_error,
        initial_chunks=initial_chunk_responses,
        reranked_chunks=reranked_chunk_responses,
        chunks=output_chunk_responses,
    )


# ---------------------------------------------------------------------------
# /ask - full pipeline (retrieval, confidence, prompt, LLM answer)
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    query: str
    session_id: str | None = None
    # ``collection_filter`` carries category names from the Node.js backend.
    # Values like ["sop", "legal"] are translated to Qdrant payload filters.
    # Pass null / omit to search the full corpus.
    collection_filter: list[str] | None = None
    # Legacy single-collection field — kept for direct API callers.
    collection: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v

    @field_validator("collection_filter")
    @classmethod
    def normalise_collection_filter(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = [item.strip().lower() for item in v if item and item.strip()]
        # Strip Swagger UI placeholder
        cleaned = [c for c in cleaned if c not in {"string", "null", "none", "default"}]
        return cleaned or None

    @field_validator("collection")
    @classmethod
    def normalize_collection(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip().lower()
        return cleaned or None


class CitationResponse(BaseModel):
    rank: int
    source_filename: str
    page_number: int | None
    section_heading: str | None
    score: float
    score_pct: int
    category: str
    extraction_method: str
    upload_date: str | None
    chunk_indices: list[int]


class AskResponse(BaseModel):
    answer: str
    was_generated: bool
    model_used: str
    chunk_count: int
    top_score: float
    confidence_passed: bool
    style_used: str
    latency_ms: float
    was_refused: bool
    refusal_message: str | None
    citations: list[CitationResponse] = Field(default_factory=list)
    faithfulness_passed: bool = True
    faithfulness_caution: str | None = None
    ocr_sources_present: bool = False
    any_stale_source: bool = False
    session_id: str | None = None


class AskQuestionRequest(BaseModel):
    query: str
    collection_filter: list[str] | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v

    @field_validator("collection_filter")
    @classmethod
    def normalize_collection_filter(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = [item.strip().lower() for item in v if item and item.strip()]
        cleaned = [c for c in cleaned if c not in {"string", "null", "none", "default"}]
        return cleaned or None


class AskQuestionResponse(BaseModel):
    answer: str
    was_generated: bool
    model_used: str
    chunk_count: int
    top_score: float
    confidence_passed: bool
    style_used: str
    latency_ms: float
    was_refused: bool
    refusal_message: str
    citations: list[CitationResponse] = Field(default_factory=list)
    faithfulness_passed: bool = True
    faithfulness_caution: str | None = None
    ocr_sources_present: bool = False
    any_stale_source: bool = False


def _citation_responses(citation_result) -> list[CitationResponse]:
    if citation_result is None:
        return []
    return [
        CitationResponse(
            rank=citation.rank,
            source_filename=citation.source_filename,
            page_number=citation.page_number,
            section_heading=citation.section_heading,
            score=citation.score,
            score_pct=citation.score_pct,
            category=citation.category,
            extraction_method=citation.extraction_method,
            upload_date=citation.upload_date,
            chunk_indices=citation.chunk_indices,
        )
        for citation in citation_result.citations
    ]


def _run_ask_pipeline(
    query: str,
    session_id: str | None,
    collection: str | list[str] | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> AskResponse:
    """Run QA pipeline and always return a user-safe response body."""
    try:
        redis_client = redis_lib.from_url(REDIS_URL)
        session = load_session(session_id, redis_client)
        state = run_pipeline(query, session, collection=collection)
        if background_tasks is not None:
            background_tasks.add_task(save_session, session_id, state.session, redis_client)

        ar   = state.answer_result
        cr   = state.confidence_result
        pr   = state.prompt_result
        rr   = state.retrieval_result
        cit  = state.citation_result
        faith = state.faithfulness_result

        return AskResponse(
            answer=cit.cited_answer if cit else (ar.answer_text if ar else ""),
            was_generated=ar.was_generated if ar else False,
            model_used=ar.model_used if ar else "",
            chunk_count=rr.chunk_count if rr else 0,
            top_score=rr.top_score if rr else 0.0,
            confidence_passed=cr.passed if cr else False,
            style_used=pr.style_used if pr else "none",
            latency_ms=ar.latency_ms if ar else 0.0,
            was_refused=rr.was_refused if rr else False,
            refusal_message=rr.refusal_message if rr else None,
            citations=_citation_responses(cit),
            faithfulness_passed=faith.passed if faith else True,
            faithfulness_caution=faith.caution_message if faith else None,
            ocr_sources_present=cit.ocr_sources_present if cit else False,
            any_stale_source=cit.any_stale_source if cit else False,
            session_id=session_id,
        )

    except Exception as exc:
        logger.exception("[QA] Pipeline failed unexpectedly: %s", exc)
        try:
            no_result = load_company_profile().qa.no_result_message
        except Exception:
            no_result = "An unexpected error occurred. Please try again."
        return AskResponse(
            answer=no_result,
            was_generated=False,
            model_used="",
            chunk_count=0,
            top_score=0.0,
            confidence_passed=False,
            style_used="none",
            latency_ms=0.0,
            was_refused=True,
            refusal_message="We could not process your request right now. Please try again.",
            citations=[],
            faithfulness_passed=True,
            faithfulness_caution=None,
            ocr_sources_present=False,
            any_stale_source=False,
        )


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, background_tasks: BackgroundTasks) -> AskResponse:
    """Run the full AI pipeline and return a generated answer.

    ``collection_filter`` (list of category names) takes priority over the
    legacy ``collection`` (single string). Both are optional — omit to search
    the full corpus.
    """
    # collection_filter (from Node.js) wins over legacy single collection string
    collection = body.collection_filter or (
        [body.collection] if body.collection else None
    )
    return _run_ask_pipeline(
        query=body.query,
        session_id=body.session_id,
        collection=collection,
        background_tasks=background_tasks,
    )


@router.post("/ask-question", response_model=AskQuestionResponse)
def ask_question(body: AskQuestionRequest) -> AskQuestionResponse:
    """
    Minimal ask-question endpoint.
    Request: {"query": "...", "collection_filter": ["sop"]}  — collection_filter is optional.
    """
    result = _run_ask_pipeline(
        query=body.query,
        session_id=None,
        collection=body.collection_filter,
    )
    return AskQuestionResponse(
        answer=result.answer,
        was_generated=result.was_generated,
        model_used=result.model_used,
        chunk_count=result.chunk_count,
        top_score=result.top_score,
        confidence_passed=result.confidence_passed,
        style_used=result.style_used,
        latency_ms=result.latency_ms,
        was_refused=result.was_refused,
        refusal_message=result.refusal_message or "",
        citations=result.citations,
        faithfulness_passed=result.faithfulness_passed,
        faithfulness_caution=result.faithfulness_caution,
        ocr_sources_present=result.ocr_sources_present,
        any_stale_source=result.any_stale_source,
    )
