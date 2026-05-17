#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Application stack — RunPod one-time setup
#
# Called automatically by runpod_start.sh on first boot.
# Safe to re-run — all steps are idempotent.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="/workspace"
VENV="$WORKSPACE/venv"

# ── [1/7] System packages ─────────────────────────────────────────────────
echo "==> [1/7] System packages"
apt-get update -qq
apt-get install -y --no-install-recommends \
    curl wget gnupg lsb-release ca-certificates \
    supervisor \
    tesseract-ocr tesseract-ocr-eng \
    libgl1 libglib2.0-0 poppler-utils \
    redis-server \
    python3-pip python3-venv \
    build-essential \
    zstd

# ── [2/7] MongoDB ─────────────────────────────────────────────────────────
echo "==> [2/7] MongoDB"
if ! command -v mongod &>/dev/null; then
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc \
        | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" \
        | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    apt-get update -qq
    apt-get install -y --no-install-recommends mongodb-org
fi
mkdir -p "$WORKSPACE/data/mongodb"

# ── [3/7] Qdrant ──────────────────────────────────────────────────────────
echo "==> [3/7] Qdrant"
if [ ! -f "$WORKSPACE/qdrant/qdrant" ]; then
    mkdir -p "$WORKSPACE/qdrant"
    curl -fsSL \
        "https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-musl.tar.gz" \
        | tar -xz --no-same-owner -C "$WORKSPACE/qdrant"
    chmod +x "$WORKSPACE/qdrant/qdrant"
fi
mkdir -p "$WORKSPACE/data/qdrant"

# ── [4/7] MinIO ───────────────────────────────────────────────────────────
echo "==> [4/7] MinIO"
if [ ! -f "$WORKSPACE/bin/minio" ]; then
    mkdir -p "$WORKSPACE/bin"
    curl -fsSL "https://dl.min.io/server/minio/release/linux-amd64/minio" \
        -o "$WORKSPACE/bin/minio"
    chmod +x "$WORKSPACE/bin/minio"
fi
mkdir -p "$WORKSPACE/data/minio"

# ── [5/7] Ollama ──────────────────────────────────────────────────────────
echo "==> [5/7] Ollama"
if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
mkdir -p "$WORKSPACE/ollama"

# ── [6/7] Python virtualenv + dependencies ────────────────────────────────
echo "==> [6/7] Python dependencies (includes torch CUDA wheels — slow)"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install \
    --no-cache-dir \
    --retries 5 \
    --extra-index-url https://download.pytorch.org/whl/cu121 \
    -r "$REPO_ROOT/ai_server/requirements.txt" -q

# ── [7/7] Node.js + server dependencies ──────────────────────────────────
# Note: Next.js client is NOT built here.
# runpod_start.sh builds it (after .env is loaded) and rebuilds automatically
# whenever NEXT_PUBLIC_API_URL changes.
echo "==> [7/7] Node.js dependencies"
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null
    apt-get install -y nodejs > /dev/null
fi
export TMPDIR=/workspace
export npm_config_cache=/workspace/npm-cache
(cd "$REPO_ROOT/server" && npm install --omit=dev --silent)
(cd "$REPO_ROOT/client" && npm install --silent)

echo ""
echo "==> Setup complete."
echo "    runpod_start.sh will now build the client and start all services."
echo ""
