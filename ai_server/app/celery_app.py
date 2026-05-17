from dotenv import load_dotenv

load_dotenv()  # must run before ai.config imports (config reads os.getenv at import time)

from celery import Celery  # noqa: E402

from ai.config import (  # noqa: E402
    CELERY_MAX_RETRIES,
    CELERY_RETRY_BACKOFF,
    CELERY_TASK_TIMEOUT_SEC,
    QUEUE_DOCUMENT_PROCESSING,
    REDIS_URL,
)

celery_app = Celery(
    "knowledge_hub",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.ingestion"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=CELERY_TASK_TIMEOUT_SEC,
    task_soft_time_limit=CELERY_TASK_TIMEOUT_SEC - 30,
    task_default_retry_delay=CELERY_RETRY_BACKOFF,
    task_annotations={
        "app.tasks.ingestion.process_document": {
            "max_retries": CELERY_MAX_RETRIES,
        },
    },
    task_routes={
        "app.tasks.ingestion.process_document": {
            "queue": QUEUE_DOCUMENT_PROCESSING,
        },
    },
    worker_prefetch_multiplier=1,
)

from celery.signals import worker_ready  # noqa: E402


@worker_ready.connect
def _preload_embedding_model(**kwargs):
    import logging as _logging
    _log = _logging.getLogger("knowledge_hub.celery_app")
    _log.info("[Worker] Preloading embedding model...")
    from ai.embeddings.loader import get_model
    get_model()
    _log.info("[Worker] Embedding model ready.")
