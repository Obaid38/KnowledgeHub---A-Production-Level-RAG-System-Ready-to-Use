import logging

from ai.config import (
    EMBEDDING_BACKEND,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    MULTILINGUAL_MODEL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_URL,
    ST_DEVICE,
    ST_MODEL_NAME,
    ST_MODEL_TRUST_REMOTE,
    ST_NORMALIZE_EMBEDDINGS,
    USE_MULTILINGUAL,
)

logger = logging.getLogger("knowledge_hub.embeddings.loader")

# Module-level singleton — loaded once on first call, reused across all requests
_model = None


def get_model():
    """Return the singleton embedding model, loading it on first call."""
    global _model
    if _model is None:
        _model = _load_model()
    return _model


def _load_model():
    """Instantiate and return the embedding model based on EMBEDDING_BACKEND."""
    logger.info(
        "[EmbeddingLoader] Loading backend=%s multilingual=%s",
        EMBEDDING_BACKEND,
        USE_MULTILINGUAL,
    )

    if EMBEDDING_BACKEND == "sentence-transformers":
        from sentence_transformers import SentenceTransformer

        model_name = MULTILINGUAL_MODEL if USE_MULTILINGUAL else ST_MODEL_NAME
        logger.info(
            "[EmbeddingLoader] Loading SentenceTransformer: %s on device=%s",
            model_name,
            ST_DEVICE,
        )
        model = SentenceTransformer(
            model_name,
            trust_remote_code=ST_MODEL_TRUST_REMOTE,
            device=ST_DEVICE,
        )
        logger.info("[EmbeddingLoader] SentenceTransformer ready.")
        return model

    if EMBEDDING_BACKEND == "ollama":
        logger.info(
            "[EmbeddingLoader] Using Ollama embedder: model=%s url=%s",
            OLLAMA_EMBED_MODEL,
            OLLAMA_URL,
        )
        return _OllamaEmbedder()

    raise ValueError(
        f"Unknown EMBEDDING_BACKEND: {EMBEDDING_BACKEND!r}. "
        f"Expected 'sentence-transformers' or 'ollama'."
    )


def embed_texts(texts: list[str], prefix: str = "") -> list[list[float]]:
    """Embed a list of texts and return a list of float vectors.

    ``prefix`` is prepended to every text before embedding (e.g. for
    nomic-embed-text task prefixes: "search_document:" or "search_query:").
    Leave empty (default) to embed texts as-is.

    Batches according to EMBEDDING_BATCH_SIZE.
    Validates each vector has length == EMBEDDING_DIM.
    """
    if not texts:
        return []

    # Apply task-instruction prefix when configured
    effective_texts = (
        [f"{prefix} {t}".strip() for t in texts] if prefix else texts
    )

    model = get_model()
    vectors: list[list[float]] = []

    if isinstance(model, _OllamaEmbedder):
        vectors = model.embed(effective_texts)
    else:
        # sentence-transformers path
        for i in range(0, len(effective_texts), EMBEDDING_BATCH_SIZE):
            batch = effective_texts[i : i + EMBEDDING_BATCH_SIZE]
            batch_vecs = model.encode(
                batch,
                normalize_embeddings=ST_NORMALIZE_EMBEDDINGS,
                show_progress_bar=False,
            )
            vectors.extend(batch_vecs.tolist())

    # Shape validation
    for idx, vec in enumerate(vectors):
        if len(vec) != EMBEDDING_DIM:
            raise ValueError(
                f"Vector[{idx}] has dim={len(vec)}, expected EMBEDDING_DIM={EMBEDDING_DIM}. "
                f"Check EMBEDDING_BACKEND and EMBEDDING_DIM in config."
            )

    logger.info(
        "[EmbeddingLoader] Embedded %d text(s) → %d vector(s) dim=%d",
        len(texts),
        len(vectors),
        EMBEDDING_DIM,
    )
    return vectors


class _OllamaEmbedder:
    """Thin wrapper around the Ollama /api/embeddings HTTP endpoint."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        vectors: list[list[float]] = []
        for text in texts:
            response = httpx.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding")
            if not embedding:
                raise ValueError(
                    f"Ollama returned no embedding for model={OLLAMA_EMBED_MODEL}. "
                    f"Response: {data}"
                )
            vectors.append(embedding)
        return vectors
