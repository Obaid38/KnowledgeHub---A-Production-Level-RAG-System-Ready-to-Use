from __future__ import annotations

import logging

from app.celery_app import celery_app
from ai.config import MINIO_BUCKET_DOCUMENTS, QDRANT_COLLECTION

logger = logging.getLogger("knowledge_hub.tasks.ingestion")


@celery_app.task(
    name="app.tasks.ingestion.process_document",
    bind=True,
    queue="document_processing",
)
def process_document(
    self,
    *,
    user_id: str,
    category: str,
    filename: str,
    bucketname: str = MINIO_BUCKET_DOCUMENTS,
    object_key: str,
    doc_id: str,
) -> dict:
    """
    Celery task — ingests a single document into Qdrant.
    Called by the Node server after a file is uploaded to MinIO.

    Document type (structured / list_heavy / narrative) is auto-detected by
    the chunker — category is accepted for backward compat but no longer
    drives chunk size.
    """
    from app.api.ingest_doucments import (
        _ensure_collection_exists,
        _download_file_bytes_from_minio,
        _ensure_supported_filename,
        _filename_from_content_disposition,
        _normalise_category,
        _run_ingestion_pipeline,
    )

    logger.info("[Task] process_document start doc_id=%s", doc_id)

    normalised_category = _normalise_category(category)
    _ensure_collection_exists(QDRANT_COLLECTION)

    file_bytes, content_type, content_disposition = _download_file_bytes_from_minio(
        bucketname, object_key
    )

    hinted = _filename_from_content_disposition(content_disposition)
    resolved_filename = _ensure_supported_filename(
        hinted or filename, doc_id, content_type
    )

    chunk_count = _run_ingestion_pipeline(
        file_bytes=file_bytes,
        filename=resolved_filename,
        doc_id=doc_id,
        category=normalised_category,
    )

    logger.info("[Task] process_document done doc_id=%s chunks=%d", doc_id, chunk_count)
    return {
        "doc_id":      doc_id,
        "user_id":     user_id,
        "category":    normalised_category,
        "collection":  QDRANT_COLLECTION,
        "chunks":      chunk_count,
        "status":      "success",
    }
