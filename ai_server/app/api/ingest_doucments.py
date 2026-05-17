from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from qdrant_client.models import Distance, SparseIndexParams, SparseVectorParams, VectorParams

from ai.config import (
    EMBEDDING_DIM,
    EMBEDDING_DOC_PREFIX,
    HYBRID_SEARCH_ENABLED,
    MAX_FILE_SIZE_BYTES,
    MINIO_BUCKET_DOCUMENTS,
    QDRANT_COLLECTION,
    QDRANT_DISTANCE_METRIC,
    SUPPORTED_EXTENSIONS,
)
from ai.embeddings.loader import embed_texts
from ai.ingestion.chunker import chunk_document
from ai.ingestion.context_prefix import build_enriched_text
from ai.ingestion.minio_client import get_s3_client
from ai.ingestion.pipeline_stage1 import run_stage1_pipeline
from ai.ingestion.qdrant_writer import delete_document_chunks, get_qdrant_client, upsert_chunks
from ai.ingestion.signals import extract_signals

logger = logging.getLogger("knowledge_hub.api.ingest_documents")
router = APIRouter(tags=["ingest_documents"])

# Recognised category values. Anything outside this list is normalised to "general".
_VALID_CATEGORIES = frozenset({
    "sop", "cases", "compliance", "finance", "legal",
    "general", "technical", "hr", "incident", "other",
})


class IngestDocumentItem(BaseModel):
    user_id:    str = Field(...,               min_length=1)
    category:   str = Field(default="general")            # optional — stored as payload metadata
    filename:   str = Field(...,               min_length=1)
    bucketname: str = Field(default=MINIO_BUCKET_DOCUMENTS, min_length=1)
    objectKey:  str = Field(...,               min_length=1)
    doc_id:     str = Field(...,               min_length=1)


def _normalise_category(value: str) -> str:
    """Return a clean, lowercase category slug, falling back to 'general'."""
    slug = value.strip().lower().replace(" ", "_") if value else "general"
    return slug if slug in _VALID_CATEGORIES else "general"


def _distance_from_config(metric: str) -> Distance:
    mapping = {
        "cosine":    Distance.COSINE,
        "dot":       Distance.DOT,
        "euclid":    Distance.EUCLID,
        "manhattan": Distance.MANHATTAN,
    }
    return mapping.get(metric.lower(), Distance.COSINE)


def _ensure_collection_exists(collection_name: str) -> None:
    client = get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        return

    distance = _distance_from_config(QDRANT_DISTANCE_METRIC)

    if HYBRID_SEARCH_ENABLED:
        # Hybrid schema: named dense vector + BM25 sparse vector.
        # Requires recreate_collection_hybrid.py to have been run first on
        # an existing collection — this path only creates fresh collections.
        client.create_collection(
            collection_name=collection_name,
            vectors_config={"dense": VectorParams(size=EMBEDDING_DIM, distance=distance)},
            sparse_vectors_config={
                "bm25": SparseVectorParams(index=SparseIndexParams(on_disk=False))
            },
        )
        logger.info(
            "[IngestAPI] Created Qdrant collection '%s' (hybrid dense+bm25)", collection_name
        )
    else:
        # Dense-only schema (default).
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=distance),
        )
        logger.info("[IngestAPI] Created Qdrant collection '%s' (dense-only)", collection_name)


def _extract_filename(file_url: str, doc_id: str) -> str:
    parsed = urlparse(file_url)
    path   = unquote(parsed.path or "")
    name   = Path(path).name.strip()
    if name:
        return name
    return f"{doc_id}.bin"


def _extension_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    mime = content_type.split(";", 1)[0].strip().lower()
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "image/jpeg": ".jpg",
        "image/png":  ".png",
        "image/tiff": ".tiff",
    }
    return mapping.get(mime)


def _filename_from_content_disposition(content_disposition: str | None) -> str | None:
    """
    Best-effort filename extraction from Content-Disposition.

    Examples:
      attachment; filename="SOP.pdf"
      attachment; filename*=UTF-8''SOP%20Document.pdf
    """
    if not content_disposition:
        return None

    header = content_disposition.strip()

    # RFC 5987 form: filename*=UTF-8''...
    m = re.search(r"filename\*\s*=\s*([^;]+)", header, flags=re.IGNORECASE)
    if m:
        value = m.group(1).strip().strip('"').strip("'")
        if "''" in value:
            _, encoded = value.split("''", 1)
            filename = unquote(encoded)
        else:
            filename = unquote(value)
        filename = Path(filename).name.strip()
        return filename or None

    # Common form: filename="..."
    m = re.search(r'filename\s*=\s*("?)([^";]+)\1', header, flags=re.IGNORECASE)
    if m:
        filename = m.group(2).strip()
        filename = Path(filename).name.strip()
        return filename or None

    return None


def _ensure_supported_filename(filename: str, doc_id: str, content_type: str | None) -> str:
    ext = Path(filename).suffix.lower()
    if ext in SUPPORTED_EXTENSIONS:
        return filename

    hinted_ext = _extension_from_content_type(content_type)
    if hinted_ext and hinted_ext in SUPPORTED_EXTENSIONS:
        return f"{Path(filename).stem or doc_id}{hinted_ext}"

    allowed = ", ".join(SUPPORTED_EXTENSIONS)
    raise ValueError(
        "Unsupported or missing file extension. "
        f"Got '{ext or '(none)'}'. Allowed: {allowed}"
    )


def _guess_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext or "bin"


def _minio_key_from_file_url(file_url: str) -> str | None:
    parsed   = urlparse(file_url)
    raw_path = unquote((parsed.path or "").strip("/"))
    if not raw_path:
        return None

    parts = [p for p in raw_path.split("/") if p]
    if not parts:
        return None

    if parts[0] == MINIO_BUCKET_DOCUMENTS:
        if len(parts) == 1:
            return None
        return "/".join(parts[1:])

    return raw_path


def _download_file_bytes_from_minio(
    bucketname: str,
    object_key: str,
) -> tuple[bytes, str | None, str | None]:
    """
    Download bytes from MinIO using S3 API.

    Returns: (bytes, content_type, content_disposition)
    """
    try:
        s3  = get_s3_client()
        obj = s3.get_object(Bucket=bucketname, Key=object_key)
        data = obj["Body"].read()
        return data, obj.get("ContentType"), obj.get("ContentDisposition")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not download object '{object_key}' from bucket '{bucketname}'.",
        ) from exc


def _run_ingestion_pipeline(
    file_bytes: bytes,
    filename: str,
    doc_id: str,
    category: str,
) -> int:
    """Run the full ingestion pipeline for one document.

    All chunks land in QDRANT_COLLECTION ("documents").
    Document type (structured / list_heavy / narrative) is auto-detected by
    the chunker from content signals — no user input required.
    ``category`` is still stored as a Qdrant payload field for optional
    filtering; it no longer drives chunk size.
    """
    stage1 = run_stage1_pipeline(file_bytes, filename)
    chunks = chunk_document(
        stage1.clean_result.text,
        [t.text for t in stage1.serialized_tables],
        [t.table_name for t in stage1.serialized_tables],
        stage1.clean_result.headings,
        category,
    )

    enriched_texts:   list[str]  = []
    chunks_with_meta: list[dict] = []

    for chunk in chunks:
        signals = extract_signals(chunk.text)
        if chunk.is_table:
            signals.has_table_data = True
            signals.table_name     = chunk.table_name

        enriched_texts.append(
            build_enriched_text(
                chunk.text,
                filename,
                chunk.heading,
                chunk.table_name,
                category,
                chunk.is_table,
            )
        )
        chunks_with_meta.append(
            {
                "text":        chunk.text,
                "heading":     chunk.heading,
                "is_table":    chunk.is_table,
                "table_name":  chunk.table_name,
                "chunk_index": chunk.chunk_index,
                "doc_type":    chunk.doc_type,   # auto-detected; stored as Qdrant payload
                "signals":     signals.__dict__,
            }
        )

    # Embed with doc prefix (e.g. "search_document:") if configured
    vectors = embed_texts(enriched_texts, prefix=EMBEDDING_DOC_PREFIX)
    if len(vectors) != len(chunks_with_meta):
        raise ValueError(
            f"Embedding count mismatch: {len(vectors)} vectors for {len(chunks_with_meta)} chunks"
        )

    # BM25 sparse vectors — only generated when hybrid search is enabled.
    # Use enriched_texts (same input as dense embeddings) so BM25 sees the
    # contextual prefix that was added for the dense model.
    sparse_vectors = None
    if HYBRID_SEARCH_ENABLED:
        from ai.ingestion.bm25_embedder import bm25_embed_texts
        sparse_vectors = bm25_embed_texts(enriched_texts)
        if sparse_vectors is None:
            logger.warning(
                "[IngestAPI] BM25 model unavailable; ingesting without sparse vectors for doc_id=%s",
                doc_id,
            )

    delete_document_chunks(QDRANT_COLLECTION, doc_id)
    return upsert_chunks(
        QDRANT_COLLECTION, doc_id, filename, category, chunks_with_meta, vectors, sparse_vectors
    )


@router.post("/ingest-documents")
def ingest_documents(payload: list[IngestDocumentItem]):
    if not payload:
        raise HTTPException(status_code=400, detail="Payload must be a non-empty array.")

    # Ensure the single universal collection exists before any ingest
    _ensure_collection_exists(QDRANT_COLLECTION)

    results: list[dict] = []
    has_errors = False

    for item in payload:
        category = _normalise_category(item.category)
        try:
            file_bytes, content_type, content_disposition = _download_file_bytes_from_minio(
                item.bucketname,
                item.objectKey,
            )
            if not file_bytes:
                raise ValueError("Downloaded file is empty.")

            if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."
                )

            # MinIO shared links often include the original filename in Content-Disposition.
            hinted_filename = _filename_from_content_disposition(content_disposition)
            filename = hinted_filename if hinted_filename else item.filename
            filename = _ensure_supported_filename(filename, item.doc_id, content_type)

            chunk_count = _run_ingestion_pipeline(
                file_bytes=file_bytes,
                filename=filename,
                doc_id=item.doc_id,
                category=category,
            )

            results.append(
                {
                    "doc_id":     item.doc_id,
                    "user_id":    item.user_id,
                    "category":   category,
                    "collection": QDRANT_COLLECTION,
                    "bucketname": item.bucketname,
                    "objectKey":  item.objectKey,
                    "status":     "success",
                    "message":    "Document successfully ingested and uploaded to Qdrant.",
                    "chunks":     chunk_count,
                }
            )
        except Exception as exc:
            has_errors = True
            logger.exception("[IngestAPI] Failed for doc_id=%s", item.doc_id)
            results.append(
                {
                    "doc_id":     item.doc_id,
                    "user_id":    item.user_id,
                    "category":   category,
                    "bucketname": item.bucketname,
                    "objectKey":  item.objectKey,
                    "status":     "error",
                    "message":    str(exc),
                }
            )

    response = {
        "api":           "ingest_documents",
        "total":         len(payload),
        "success_count": sum(1 for r in results if r["status"] == "success"),
        "error_count":   sum(1 for r in results if r["status"] == "error"),
        "results":       results,
    }

    if has_errors:
        return JSONResponse(status_code=207, content=response)
    return response
