import logging

from ai.config import EMBEDDING_QUERY_PREFIX, HYBRID_SEARCH_ENABLED
from ai.embeddings.loader import embed_texts

logger = logging.getLogger("knowledge_hub.retrieval.query_embedder")


def embed_query(query_text: str) -> list[float]:
    """Embed a query string using the same model and backend as ingestion.

    Applies EMBEDDING_QUERY_PREFIX (e.g. "search_query:") when configured —
    this must match the document prefix used at ingest time for models that
    support task-instruction prefixes (nomic-embed-text, mxbai-embed-large).

    Reuses ai.embeddings.loader.embed_texts() to guarantee vector-space
    consistency. Handles both sentence-transformers (local) and Ollama (RunPod).

    Raises RuntimeError if the embedding backend is unreachable.
    """
    try:
        vectors = embed_texts([query_text], prefix=EMBEDDING_QUERY_PREFIX)
    except Exception as exc:
        raise RuntimeError(
            f"Embedding failed — check that Ollama/model is running. Detail: {exc}"
        ) from exc

    vec = vectors[0]
    logger.info("[QueryEmbedder] Embedded query → dim=%d", len(vec))
    return vec


def bm25_embed_query(query_text: str):
    """Generate a BM25 sparse embedding for the query.

    Returns a SparseEmbedding object when HYBRID_SEARCH_ENABLED=true and the
    BM25 model is available, otherwise returns None (fail-open — callers fall
    back to dense-only search when None is returned).

    Uses fastembed query_embed() which applies query-specific BM25 weighting,
    distinct from the document-side embed() used at ingest time.
    """
    if not HYBRID_SEARCH_ENABLED:
        return None
    from ai.ingestion.bm25_embedder import bm25_embed_query as _bm25_embed
    result = _bm25_embed(query_text)
    if result is not None:
        logger.debug("[QueryEmbedder] BM25 sparse query → indices=%d", len(result.indices))
    return result
