import os

# ── Chunking — adaptive document-type detection ───────────────────────────────
# Chunk sizes are no longer driven by a user-selected category.
# The chunker analyses each document's content and auto-classifies it into one
# of three structural types, then picks the matching size/overlap config.
#
#   structured  — many headings / numbered sections (SOPs, manuals, policies)
#   list_heavy  — many bullets / short numbered steps (procedures, checklists)
#   narrative   — few/no headings, dense paragraphs (reports, emails, legal, cases)
#
# All values are env-overridable so RunPod tuning never requires code changes.
DOCUMENT_TYPE_CHUNK_CONFIG: dict = {
    "structured": {
        "size":    int(os.getenv("CHUNK_SIZE_STRUCTURED",    "700")),
        "overlap": int(os.getenv("CHUNK_OVERLAP_STRUCTURED", "100")),
    },
    "list_heavy": {
        "size":    int(os.getenv("CHUNK_SIZE_LIST_HEAVY",    "600")),
        "overlap": int(os.getenv("CHUNK_OVERLAP_LIST_HEAVY", "120")),
    },
    "narrative": {
        "size":    int(os.getenv("CHUNK_SIZE_NARRATIVE",     "1000")),
        "overlap": int(os.getenv("CHUNK_OVERLAP_NARRATIVE",  "150")),
    },
}

# Detection thresholds — fraction of non-blank lines that trigger each type.
# heading_ratio  ≥ 0.05  → "structured"
# bullet_ratio   ≥ 0.15  → "list_heavy"   (also triggers when avg line len ≤ max)
# avg_line_len   ≤ 60    → "list_heavy"
# otherwise              → "narrative"
DOC_TYPE_HEADING_RATIO    = float(os.getenv("DOC_TYPE_HEADING_RATIO",    "0.05"))
DOC_TYPE_BULLET_RATIO     = float(os.getenv("DOC_TYPE_BULLET_RATIO",     "0.15"))
DOC_TYPE_AVG_LINE_LEN_MAX = int(os.getenv("DOC_TYPE_AVG_LINE_LEN_MAX",   "60"))

# Global fallback defaults (used only when DOCUMENT_TYPE_CHUNK_CONFIG lookup fails).
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",    "700"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

# ── Backward-compat aliases ───────────────────────────────────────────────────
# debug_retrieval.py and other scripts still import these names.
# CATEGORY_CHUNK_CONFIG is kept with the same structure; USE_CATEGORY_CHUNKING
# is now always False — the chunker auto-detects instead.
CATEGORY_CHUNK_CONFIG: dict = {
    "sop":        {"size": 700,  "overlap": 100},
    "cases":      {"size": 1000, "overlap": 150},
    "compliance": {"size": 700,  "overlap": 100},
    "finance":    {"size": 700,  "overlap": 100},
    "legal":      {"size": 1000, "overlap": 150},
    "general":    {"size": 700,  "overlap": 100},
    "technical":  {"size": 700,  "overlap": 100},
    "hr":         {"size": 700,  "overlap": 100},
    "incident":   {"size": 700,  "overlap": 100},
}
USE_CATEGORY_CHUNKING = False  # superseded by auto-detection

# ── File limits ──────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB    = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SUPPORTED_EXTENSIONS: list = [
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
]

# ── OCR ──────────────────────────────────────────────────────────────────────
OCR_ENGINE                        = os.getenv("OCR_ENGINE", "tesseract")
OCR_LANGUAGES                     = os.getenv("OCR_LANGUAGES", "eng")
OCR_DPI                           = int(os.getenv("OCR_DPI", "300"))
PDF_MIN_CHARS_BEFORE_OCR_FALLBACK = int(os.getenv("PDF_MIN_CHARS_BEFORE_OCR_FALLBACK", "100"))

# ── Qdrant ───────────────────────────────────────────────────────────────────
# Single universal collection — all documents land here regardless of category.
# Category is stored as a payload field on each chunk so retrieval can apply
# a payload filter when the user scopes their search to specific categories.
#
# Changing QDRANT_COLLECTION after first ingest requires:
#   1. Delete old Qdrant collection
#   2. Re-create with the new name
#   3. Re-ingest all documents
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents")

# Backward-compat aliases (code that still imports QDRANT_COLLECTIONS or
# QDRANT_DEFAULT_COLLECTION continues to work without changes).
QDRANT_COLLECTIONS        = [QDRANT_COLLECTION]
QDRANT_DEFAULT_COLLECTION = QDRANT_COLLECTION
QDRANT_DISTANCE_METRIC    = "Cosine"

# ── MinIO ────────────────────────────────────────────────────────────────────
MINIO_BUCKET_DOCUMENTS = os.getenv("MINIO_BUCKET_DOCUMENTS", "knowledge-hub-docs")

# ── Celery ───────────────────────────────────────────────────────────────────
QUEUE_DOCUMENT_PROCESSING = "document_processing"
QUEUE_EMBEDDINGS          = "embeddings"
QUEUE_QA                  = "qa"
QUEUE_MAINTENANCE         = "maintenance"
CELERY_TASK_TIMEOUT_SEC   = int(os.getenv("CELERY_TASK_TIMEOUT_SEC", "600"))
CELERY_MAX_RETRIES        = int(os.getenv("CELERY_MAX_RETRIES", "3"))
CELERY_RETRY_BACKOFF      = int(os.getenv("CELERY_RETRY_BACKOFF", "60"))

# ── Context enrichment ───────────────────────────────────────────────────────
# Prepend "[Document: X] [Section: Y] [Category: Z]\n" before embedding.
# Enriched text is embedded; original clean text is stored in Qdrant payload.
ENABLE_CONTEXTUAL_PREFIX = os.getenv("ENABLE_CONTEXTUAL_PREFIX", "true").lower() == "true"

# ── Staleness ────────────────────────────────────────────────────────────────
DOCUMENT_STALENESS_DAYS = int(os.getenv("DOCUMENT_STALENESS_DAYS", "365"))
