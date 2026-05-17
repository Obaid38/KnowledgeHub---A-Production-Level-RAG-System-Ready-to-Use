import os

from ai.config.config_env import IS_LOCAL

# Redis (Celery broker + result backend)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379" if IS_LOCAL else "redis://redis:6379")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost" if IS_LOCAL else "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# MinIO
MINIO_URL = os.getenv("MINIO_URL", "http://localhost:9000" if IS_LOCAL else "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333" if IS_LOCAL else "http://qdrant:6333")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost" if IS_LOCAL else "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Ollama (RunPod only - not used locally)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434" if IS_LOCAL else "http://ollama:11434")
