import os

from ai.config.config_env import IS_LOCAL

EMBEDDING_BACKEND = os.getenv(
    "EMBEDDING_BACKEND", "sentence-transformers" if IS_LOCAL else "ollama"
)

# ── sentence-transformers (local CPU/GPU) ─────────────────────────────────────
# Model options (set ST_MODEL_NAME + matching EMBEDDING_DIM):
#   nomic-ai/nomic-embed-text-v1          768-d  strong English               CURRENT DEFAULT
#   sentence-transformers/all-mpnet-base-v2 768-d  solid general-purpose baseline
#   mixedbread-ai/mxbai-embed-large-v1   1024-d  top MTEB English, upgrade path
#     → set ST_MODEL_NAME=mixedbread-ai/mxbai-embed-large-v1, EMBEDDING_DIM=1024
#     → delete Qdrant collection and re-ingest everything
ST_MODEL_NAME           = os.getenv("ST_MODEL_NAME", "nomic-ai/nomic-embed-text-v1")
ST_MODEL_TRUST_REMOTE   = True
ST_DEVICE               = os.getenv("ST_DEVICE", "cpu" if IS_LOCAL else "cuda")
ST_NORMALIZE_EMBEDDINGS = True

# ── Ollama (RunPod GPU) ───────────────────────────────────────────────────────
# Model options (set OLLAMA_EMBED_MODEL + matching EMBEDDING_DIM):
#   nomic-embed-text          768-d   strong English, fast           CURRENT DEFAULT
#     → ollama pull nomic-embed-text
#   mxbai-embed-large         1024-d  best quality, recommended upgrade
#     → ollama pull mxbai-embed-large; set EMBEDDING_DIM=1024; re-ingest
#   qwen3-embedding:4b-fp16   2560-d  highest quality, ~300ms/chunk on A100
#     → for future use; set EMBEDDING_DIM=2560; full re-ingest required
#
# NEVER change OLLAMA_EMBED_MODEL alone. You MUST also:
#   1. Update EMBEDDING_DIM to match the new model's output dimension
#   2. Delete and recreate the Qdrant collection (dimension mismatch = ValueError)
#   3. Re-ingest all documents
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# ── Task instruction prefixes ─────────────────────────────────────────────────
# nomic-embed-text and mxbai-embed-large both support task-instruction prefixes
# that improve retrieval quality by telling the model whether it is embedding
# a document or a query.
#
# Activate when doing a full re-ingest with a prefix-aware model:
#   EMBEDDING_DOC_PREFIX=search_document:
#   EMBEDDING_QUERY_PREFIX=search_query:
#
# These MUST be set consistently across ingestion AND retrieval.
# Leave blank to preserve existing embeddings (current behavior, no prefix).
EMBEDDING_DOC_PREFIX   = os.getenv("EMBEDDING_DOC_PREFIX",   "")
EMBEDDING_QUERY_PREFIX = os.getenv("EMBEDDING_QUERY_PREFIX", "")

# ── Shared ────────────────────────────────────────────────────────────────────
# EMBEDDING_DIM must match the model's output dimension exactly.
# Mismatch causes a ValueError during ingest — check this first if ingest fails.
EMBEDDING_DIM        = int(os.getenv("EMBEDDING_DIM", "768"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32" if IS_LOCAL else "128"))

# ── Multilingual ─────────────────────────────────────────────────────────────
# Activate if Arabic or other non-English documents are confirmed present.
# When USE_MULTILINGUAL=true, also set EMBEDDING_DIM=1024.
MULTILINGUAL_MODEL = os.getenv("MULTILINGUAL_MODEL", "intfloat/multilingual-e5-large")
USE_MULTILINGUAL   = os.getenv("USE_MULTILINGUAL", "false").lower() == "true"
