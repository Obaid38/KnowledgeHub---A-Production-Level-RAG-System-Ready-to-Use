import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.encoders import jsonable_encoder

load_dotenv()  # load .env before importing any ai.config values

from ai.config import (  # noqa: E402
    ACTIVE_ENV_LABEL,
    DEBUG,
    EMBEDDING_DIM,
    LOG_LEVEL,
    MINIO_ACCESS_KEY,
    MINIO_BUCKET_DOCUMENTS,
    MINIO_SECRET_KEY,
    MINIO_URL,
    QDRANT_COLLECTIONS,
    QDRANT_DISTANCE_METRIC,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_URL,
    REDIS_URL,
)
from ai.config.company_profile import load_company_profile
from app.api.ingest_doucments import router as ingest_documents_router
from app.api.routes.qa import router as qa_router

logging.basicConfig(level=getattr(logging, LOG_LEVEL, "INFO"))
logger = logging.getLogger("knowledge_hub")


def _qdrant_distance_from_config(metric: str):
    from qdrant_client.models import Distance

    mapping = {
        "cosine": Distance.COSINE,
        "dot": Distance.DOT,
        "euclid": Distance.EUCLID,
        "manhattan": Distance.MANHATTAN,
    }
    return mapping.get(metric.lower(), Distance.COSINE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Print active environment
    logger.info(ACTIVE_ENV_LABEL)

    # MinIO - create bucket if not exists
    try:
        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_URL,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
        )
        try:
            s3.head_bucket(Bucket=MINIO_BUCKET_DOCUMENTS)
            logger.info("[MinIO] Bucket '%s' already exists", MINIO_BUCKET_DOCUMENTS)
        except ClientError as bucket_err:
            error_code = str(bucket_err.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchBucket", "NotFound"}:
                s3.create_bucket(Bucket=MINIO_BUCKET_DOCUMENTS)
                logger.info("[MinIO] Created bucket '%s'", MINIO_BUCKET_DOCUMENTS)
            else:
                raise
    except Exception as exc:
        logger.error("[MinIO] Startup error: %s", exc)

    # Qdrant - create all collections if not exist
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams

        qclient = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        existing = {collection.name for collection in qclient.get_collections().collections}

        for name in QDRANT_COLLECTIONS:
            if name not in existing:
                qclient.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=_qdrant_distance_from_config(QDRANT_DISTANCE_METRIC),
                    ),
                )
                logger.info("[Qdrant] Created collection '%s'", name)
            else:
                logger.info("[Qdrant] Collection '%s' already exists", name)
    except Exception as exc:
        logger.error("[Qdrant] Startup error: %s", exc)

    yield


app = FastAPI(
    title=f"{load_company_profile().brand.app_name} AI Server",
    version="0.1.0",
    debug=DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers ensure all 4xx/5xx responses include a `message`
# field so that axios interceptors can surface meaningful feedback to the UI.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = errors[0]["msg"] if errors else "Validation error"
    return JSONResponse(
        status_code=400,
        # FastAPI's error structure may include non-JSON-serializable objects
        # (e.g. `ValueError` inside `ctx`), so we normalize it first.
        content={"message": msg, "detail": jsonable_encoder(errors)},
    )


app.include_router(ingest_documents_router, prefix="/api")
app.include_router(qa_router, prefix="/api/qa")


@app.get("/api/health")
def health_check():
    results = {}

    # Redis
    try:
        import redis as redis_lib

        redis_client = redis_lib.from_url(REDIS_URL, socket_connect_timeout=2)
        redis_client.ping()
        results["redis"] = {"status": "ok"}
    except Exception as exc:
        results["redis"] = {"status": "error", "detail": str(exc)}

    # MinIO
    try:
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_URL,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
        )
        s3.list_buckets()
        results["minio"] = {"status": "ok"}
    except Exception as exc:
        results["minio"] = {"status": "error", "detail": str(exc)}

    # Qdrant
    try:
        from qdrant_client import QdrantClient

        qclient = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        qclient.get_collections()
        results["qdrant"] = {"status": "ok"}
    except Exception as exc:
        results["qdrant"] = {"status": "error", "detail": str(exc)}

    results["config"] = {
        "qdrant_url": QDRANT_URL,
    }

    return results
