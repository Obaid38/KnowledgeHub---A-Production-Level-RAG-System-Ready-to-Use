import os

ENV = os.getenv("ENV", "local")
IS_LOCAL = ENV == "local"
IS_RUNPOD = ENV == "runpod"
ACTIVE_ENV_LABEL = f"[CONFIG] Active environment: {ENV.upper()}"
