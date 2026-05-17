from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    chunk_id: str           # Qdrant point ID
    chunk_text: str         # Original stored chunk text (NOT the prefixed version)
    score: float            # Cosine similarity score from Qdrant
    doc_id: str             # UUID of the source document
    source_filename: str    # Original filename — used for citations
    category: str           # Collection slug (e.g. "sop", "cases")
    section_heading: str    # Nearest heading above this chunk
    page_number: int | None # Page number if extracted
    access_level: str       # public / internal / restricted / confidential
    extraction_method: str  # direct_pdf / ocr / structured_parse
    upload_date: str        # ISO 8601 ingestion date
    language: str           # ISO 639-1 (e.g. "en")
    chunk_index: int        # Position of this chunk within its document
    rerank_score: float | None = None  # Cross-encoder relevance score when reranked


@dataclass
class RetrievalResult:
    query_text: str                          # Original query as received
    collection_searched: str                 # Qdrant collection that was queried
    chunks: list[RetrievedChunk] = field(default_factory=list)  # Ordered by score descending
    top_score: float = 0.0                   # Score of best chunk (0.0 if no results)
    score_distribution: list[float] = field(default_factory=list)  # All scores for monitoring
    threshold_applied: float = 0.0           # The score threshold used
    empty: bool = True                       # True if no chunks passed the threshold
    below_threshold_count: int = 0           # How many chunks were found but rejected
    latency_ms: float = 0.0                  # Total retrieval time in milliseconds
