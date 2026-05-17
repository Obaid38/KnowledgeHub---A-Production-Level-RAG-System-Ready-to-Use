"""BM25 sparse embedding for hybrid search.

Wraps the fastembed SparseTextEmbedding model as a lazy-loaded singleton.
Only imported and loaded when HYBRID_SEARCH_ENABLED=true — zero cost when
hybrid search is disabled.

fastembed distinguishes between document embeddings (embed) and query
embeddings (query_embed). Use embed() at ingest time and query_embed() at
retrieval time to apply the correct BM25 term-weighting for each role.
"""

from __future__ import annotations

import logging

from ai.config import BM25_MODEL_NAME

logger = logging.getLogger("knowledge_hub.ingestion.bm25_embedder")

_bm25_model = None
_load_attempted = False


def _get_bm25_model():
    """Return the module-level singleton SparseTextEmbedding model.

    Loads on first call; subsequent calls return the cached instance.
    Returns None if the model fails to load (fail-open — callers should
    skip BM25 when None is returned).
    """
    global _bm25_model, _load_attempted
    if _bm25_model is not None:
        return _bm25_model
    if _load_attempted:
        return None
    _load_attempted = True

    try:
        from fastembed import SparseTextEmbedding

        logger.info("[BM25Embedder] Loading model=%s", BM25_MODEL_NAME)
        _bm25_model = SparseTextEmbedding(BM25_MODEL_NAME)
        logger.info("[BM25Embedder] Loaded model=%s", BM25_MODEL_NAME)
    except Exception as exc:
        logger.warning("[BM25Embedder] Load failed; BM25 unavailable: %s", exc)
        _bm25_model = None

    return _bm25_model


def bm25_embed_texts(texts: list[str]) -> list | None:
    """Generate BM25 sparse embeddings for a list of document texts.

    Returns a list of SparseEmbedding objects (one per text) in the same
    order as the input, or None if the model is unavailable.

    Use this at ingest time (document side of BM25).
    """
    model = _get_bm25_model()
    if model is None:
        return None
    try:
        return list(model.embed(texts))
    except Exception as exc:
        logger.warning("[BM25Embedder] embed() failed: %s", exc)
        return None


def bm25_embed_query(query_text: str):
    """Generate a BM25 sparse embedding for a single query string.

    Returns a SparseEmbedding object or None if the model is unavailable.

    Use this at retrieval time (query side of BM25). fastembed applies
    query-specific term weighting via query_embed(), which differs from
    the document-side embed() and should be used consistently here.
    """
    model = _get_bm25_model()
    if model is None:
        return None
    try:
        return next(iter(model.query_embed(query_text)))
    except Exception as exc:
        logger.warning("[BM25Embedder] query_embed() failed: %s", exc)
        return None
