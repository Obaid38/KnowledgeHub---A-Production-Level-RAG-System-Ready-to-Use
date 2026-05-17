import os
from pathlib import Path

from ai.config.config_env import IS_LOCAL

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

DEBUG = os.getenv("DEBUG", "true" if IS_LOCAL else "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if IS_LOCAL else "INFO")
LOG_CELERY_TASK_BODY = os.getenv("LOG_CELERY_TASK_BODY", "true" if IS_LOCAL else "false").lower() == "true"

BASE_DIR = Path(__file__).resolve().parent.parent  # ai/
MODELS_DIR = Path(os.getenv("MODELS_DIR", str(BASE_DIR / "models")))
TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp/knowledge-hub"))
try:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    TEMP_DIR = BASE_DIR / "tmp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
