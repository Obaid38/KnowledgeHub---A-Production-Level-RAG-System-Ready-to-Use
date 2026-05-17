"""Cross-encoder reranking for retrieved chunks.

The reranker is intentionally fail-open: if the model cannot be loaded or a
prediction fails, callers receive the original vector-ranked chunks.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import TypeVar

from ai.config import RERANKER_DEVICE, RERANKER_ENABLED, RERANKER_MODEL

logger = logging.getLogger("knowledge_hub.retrieval.reranker")

TChunk = TypeVar("TChunk")

_model = None
_load_attempted = False


def rerank_chunks(query: str, chunks: Sequence[TChunk], top_k: int) -> list[TChunk]:
    """Return chunks reranked by a sentence-transformers CrossEncoder."""
    if not RERANKER_ENABLED or not chunks or top_k <= 0:
        return list(chunks)

    model = _get_model()
    if model is None:
        return list(chunks)

    pairs = [(query, _chunk_text(chunk)) for chunk in chunks]
    try:
        scores = model.predict(pairs, batch_size=16, show_progress_bar=False)
    except Exception as exc:
        logger.warning("[Reranker] Prediction failed; using vector ranking: %s", exc)
        return list(chunks)

    scored_chunks = []
    for original_rank, (chunk, score) in enumerate(zip(chunks, scores)):
        rerank_score = float(score)
        _attach_rerank_score(chunk, rerank_score)
        scored_chunks.append((rerank_score, original_rank, chunk))

    scored_chunks.sort(key=lambda item: (-item[0], item[1]))
    reranked = [chunk for _, _, chunk in scored_chunks[:top_k]]
    logger.info(
        "[Reranker] model=%s candidates=%d returned=%d top_rerank_score=%.4f",
        RERANKER_MODEL,
        len(chunks),
        len(reranked),
        scored_chunks[0][0] if scored_chunks else 0.0,
    )
    return reranked


def _get_model():
    global _load_attempted, _model
    if _model is not None:
        return _model
    if _load_attempted:
        return None
    _load_attempted = True

    try:
        from sentence_transformers import CrossEncoder

        resolved_device = _resolve_device(RERANKER_DEVICE)
        start = time.perf_counter()
        logger.info(
            "[Reranker] Loading model=%s device=%s requested_device=%s",
            RERANKER_MODEL,
            resolved_device,
            RERANKER_DEVICE,
        )
        _model = CrossEncoder(RERANKER_MODEL, device=resolved_device)
        logger.info(
            "[Reranker] Loaded model=%s device=%s latency=%.0fms",
            RERANKER_MODEL,
            resolved_device,
            (time.perf_counter() - start) * 1000,
        )
    except Exception as exc:
        logger.warning("[Reranker] Load failed; using vector ranking: %s", exc)
        _model = None

    return _model


def _chunk_text(chunk: object) -> str:
    value = getattr(chunk, "chunk_text", "")
    return value if isinstance(value, str) else str(value or "")


def _resolve_device(requested_device: str) -> str:
    normalized = (requested_device or "").strip().lower()
    if not normalized.startswith("cuda"):
        return requested_device

    try:
        import torch

        if torch.cuda.is_available():
            return requested_device
    except Exception as exc:
        logger.warning("[Reranker] CUDA preflight failed; falling back to CPU: %s", exc)
        return "cpu"

    logger.warning("[Reranker] CUDA requested but unavailable; falling back to CPU")
    return "cpu"


def _attach_rerank_score(chunk: object, score: float) -> None:
    try:
        setattr(chunk, "rerank_score", score)
    except Exception:
        pass
