# ─────────────────────────────────────────────────────────────────────────────
# AI Server
# Base: CUDA 12.1 runtime — gives the Celery worker GPU access for the
# sentence-transformers reranker and any ST fallback paths.
# Ollama (separate service) handles LLM + embedding inference on the A100.
# ─────────────────────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies:
#   python3.11        — runtime
#   tesseract-ocr     — OCR extraction (pytesseract)
#   libgl1            — OpenCV / pymupdf shared lib
#   libglib2.0-0      — GLib (required by libgl1 on headless systems)
#   poppler-utils     — pdfplumber needs pdfinfo/pdftotext
#   curl              — healthcheck + ollama model pulls
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

WORKDIR /app

COPY requirements.txt .

# Install torch from the CUDA wheel index first so pip finds the GPU-enabled
# wheel when it later processes torch== in requirements.txt.
# --extra-index-url means PyPI is still checked for all other packages.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cu121 \
        -r requirements.txt

# Copy application source (agents.yml lives inside ai/)
COPY app/ ./app/
COPY ai/  ./ai/
COPY scripts/ ./scripts/

EXPOSE 8000

# Default: run the FastAPI server.
# Override in docker-compose (worker service) with the celery command.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
