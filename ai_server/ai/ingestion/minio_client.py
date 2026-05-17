import logging

import boto3

from ai.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET_DOCUMENTS,
    MINIO_SECRET_KEY,
    MINIO_URL,
)

logger = logging.getLogger("knowledge_hub.minio")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_URL,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def upload_file_to_minio(
    file_bytes: bytes,
    doc_id: str,
    filename: str,
    user_category: str | None = None,
) -> str:
    category_prefix = (user_category or "general").strip().lower().replace(" ", "_")
    minio_path = f"{category_prefix}/{doc_id}/{filename}"
    s3 = get_s3_client()
    s3.put_object(
        Bucket=MINIO_BUCKET_DOCUMENTS,
        Key=minio_path,
        Body=file_bytes,
    )
    logger.info("[MinIO] Uploaded %s (%d bytes)", minio_path, len(file_bytes))
    return minio_path


def download_file_from_minio(minio_path: str) -> bytes:
    s3 = get_s3_client()
    response = s3.get_object(Bucket=MINIO_BUCKET_DOCUMENTS, Key=minio_path)
    data = response["Body"].read()
    logger.info("[MinIO] Downloaded %s (%d bytes)", minio_path, len(data))
    return data


def delete_file_from_minio(minio_path: str) -> None:
    s3 = get_s3_client()
    s3.delete_object(Bucket=MINIO_BUCKET_DOCUMENTS, Key=minio_path)
    logger.info("[MinIO] Deleted %s", minio_path)
