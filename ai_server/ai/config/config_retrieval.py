import os

from ai.config.config_env import IS_LOCAL

# ── Vector retrieval ──────────────────────────────────────────────────────────
# PRE_RERANK: candidates fetched from Qdrant before reranking.
# Keep high (80) so the reranker has a rich candidate pool.
# POST_RERANK: final chunks returned after reranking; Step 3 applies a
# per-style cap (max_chunks_by_style in agents.yml) on top of this.
RETRIEVAL_TOP_K_PRE_RERANK  = int(os.getenv("RETRIEVAL_TOP_K_PRE_RERANK",  "80"))
RETRIEVAL_TOP_K_POST_RERANK = int(os.getenv("RETRIEVAL_TOP_K_POST_RERANK", "15"))

# Cosine similarity threshold — intentionally loose (garbage filter only).
# Applied only to the dense Prefetch leg of hybrid search.
# When HYBRID_SEARCH_ENABLED=true the RRF result is NOT filtered by this
# threshold (RRF scores are not cosine similarities); the reranker acts as
# the precision gate for the final ranked list.
# 0.35 suits nomic-embed-text. If switching to mxbai-embed-large, start at 0.40.
RETRIEVAL_SCORE_THRESHOLD = float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.35"))

# ── Reranker ──────────────────────────────────────────────────────────────────
# Disabled locally (CPU too slow), enabled on RunPod A100.
#
# Model options — all are CrossEncoder-compatible, swap via RERANKER_MODEL env var:
#   cross-encoder/ms-marco-MiniLM-L-6-v2   fast baseline, CPU-friendly        (local default)
#   BAAI/bge-reranker-v2-m3                strong multilingual, A100-safe      (RunPod default)
#   BAAI/bge-reranker-v2-gemma             2.5B, best quality, ~200ms/50 cands (current RunPod)
#
# To upgrade: set RERANKER_MODEL=BAAI/bge-reranker-v2-gemma in .env, restart API.
# NOTE: Qwen3-Reranker-4B is even stronger but requires a custom causal-LM
# yes/no scoring implementation — do not use as a plain CrossEncoder name swap.
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false" if IS_LOCAL else "true").lower() == "true"
RERANKER_MODEL   = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANKER_DEVICE  = os.getenv("RERANKER_DEVICE", "cpu" if IS_LOCAL else "cuda")

# ── Hybrid search (dense + sparse BM25) ───────────────────────────────────────
# Requires Qdrant collection created with sparse_vectors_config and sparse
# vectors populated at ingestion time (bm25_embedder.py + qdrant_writer.py).
# Set HYBRID_SEARCH_ENABLED=true only after running recreate_collection_hybrid.py
# and re-ingesting all documents.
#
# Fusion strategy: Qdrant native Reciprocal Rank Fusion (RRF).
# RRF normalises by rank position — no score calibration needed.
# HYBRID_DENSE_WEIGHT / HYBRID_SPARSE_WEIGHT are retained for future
# weighted-RRF tuning but are not used in the current RRF implementation.
HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "false").lower() == "true"
HYBRID_DENSE_WEIGHT   = float(os.getenv("HYBRID_DENSE_WEIGHT",  "0.7"))
HYBRID_SPARSE_WEIGHT  = float(os.getenv("HYBRID_SPARSE_WEIGHT", "0.3"))

# BM25 sparse embedding model (fastembed).
# "Qdrant/bm25" is the recommended model for Qdrant native sparse vectors.
# Only loaded when HYBRID_SEARCH_ENABLED=true.
BM25_MODEL_NAME = os.getenv("BM25_MODEL_NAME", "Qdrant/bm25")
