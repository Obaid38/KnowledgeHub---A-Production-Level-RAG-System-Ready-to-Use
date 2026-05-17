#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Application stack — RunPod start script
#
# The ONLY command you need after cloning and filling in .env:
#   bash scripts/runpod_start.sh
#
# First run:  auto-runs setup (~15 min), then starts everything.
# Every run after that: just restarts services (< 30 sec).
# Data in /workspace persists across pod restarts.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="/workspace"
VENV="$WORKSPACE/venv"
SOCK="/tmp/ihub-supervisor.sock"
CONF="/tmp/ihub-supervisord.conf"
WRAPPERS="/tmp/ihub-wrappers"

# ── Guard: .env must exist ────────────────────────────────────────────────
if [ ! -f "$REPO_ROOT/.env" ]; then
    echo ""
    echo "  ERROR: .env not found."
    echo "  Run:   cp .env.runpod .env  then fill in all REPLACE_WITH_* values."
    echo ""
    exit 1
fi

# ── Auto-run setup on first boot ──────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo "==> First run detected — running setup (~15 min)..."
    bash "$REPO_ROOT/scripts/runpod_setup.sh"
fi

# ── Load env ──────────────────────────────────────────────────────────────
set -a; source "$REPO_ROOT/.env"; set +a

# ── Rebuild Next.js if NEXT_PUBLIC_API_URL changed since last build ───────
CACHE_FILE="$WORKSPACE/.last_client_api_url"
CURRENT_URL="${NEXT_PUBLIC_API_URL:-}"
LAST_URL="$(cat "$CACHE_FILE" 2>/dev/null || echo '')"

if [ ! -d "$REPO_ROOT/client/.next" ] || [ "$CURRENT_URL" != "$LAST_URL" ]; then
    echo "==> Building Next.js client (NEXT_PUBLIC_API_URL changed or first build)..."
    (cd "$REPO_ROOT/client" && npm run build)
    echo "$CURRENT_URL" > "$CACHE_FILE"
fi

# ── Generate per-service wrapper scripts (source .env at runtime) ─────────
# supervisord has no native envfile support — wrappers solve this cleanly.
mkdir -p "$WRAPPERS" "$WORKSPACE/logs"

mk_wrapper() {
    local name="$1" dir="$2" cmd="$3"
    cat > "$WRAPPERS/$name.sh" <<WRAPPER
#!/bin/bash
set -a; source "$REPO_ROOT/.env"; set +a
cd "$dir"
exec env $cmd
WRAPPER
    chmod +x "$WRAPPERS/$name.sh"
}

mk_wrapper "api" \
    "$REPO_ROOT/ai_server" \
    "PYTHONPATH=$REPO_ROOT/ai_server $VENV/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"

mk_wrapper "worker" \
    "$REPO_ROOT/ai_server" \
    "PYTHONPATH=$REPO_ROOT/ai_server $VENV/bin/celery -A app.celery_app worker --loglevel=info -Q document_processing,embeddings -c 2"

mk_wrapper "server" \
    "$REPO_ROOT/server" \
    "node src/server.js"

mk_wrapper "client" \
    "$REPO_ROOT/client" \
    "PORT=3000 npm start"

# ── Generate supervisord config ────────────────────────────────────────────
cat > "$CONF" <<SUPCONF
[supervisord]
nodaemon=false
logfile=$WORKSPACE/logs/supervisord.log
pidfile=/tmp/ihub-supervisord.pid

[unix_http_server]
file=$SOCK

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix://$SOCK

; ── Infrastructure ──────────────────────────────────────────────────────────

[program:mongodb]
command=mongod --dbpath $WORKSPACE/data/mongodb --bind_ip 127.0.0.1 --quiet
autostart=true
autorestart=true
stdout_logfile=$WORKSPACE/logs/mongodb.log
redirect_stderr=true

[program:redis]
command=redis-server --bind 127.0.0.1 --loglevel warning
autostart=true
autorestart=true
stdout_logfile=$WORKSPACE/logs/redis.log
redirect_stderr=true

[program:qdrant]
command=$WORKSPACE/qdrant/qdrant
directory=$WORKSPACE/qdrant
environment=QDRANT__STORAGE__STORAGE_PATH="$WORKSPACE/data/qdrant"
autostart=true
autorestart=true
stdout_logfile=$WORKSPACE/logs/qdrant.log
redirect_stderr=true

[program:minio]
command=$WORKSPACE/bin/minio server $WORKSPACE/data/minio --console-address :9001
environment=MINIO_ROOT_USER="minioadmin",MINIO_ROOT_PASSWORD="minioadmin"
autostart=true
autorestart=true
stdout_logfile=$WORKSPACE/logs/minio.log
redirect_stderr=true

[program:ollama]
command=ollama serve
environment=OLLAMA_HOST="0.0.0.0",OLLAMA_MODELS="$WORKSPACE/ollama"
autostart=true
autorestart=true
stdout_logfile=$WORKSPACE/logs/ollama.log
redirect_stderr=true

; ── Application ─────────────────────────────────────────────────────────────

[program:api]
command=$WRAPPERS/api.sh
autostart=true
autorestart=true
startsecs=15
stdout_logfile=$WORKSPACE/logs/api.log
redirect_stderr=true

[program:worker]
command=$WRAPPERS/worker.sh
autostart=true
autorestart=true
startsecs=15
stdout_logfile=$WORKSPACE/logs/worker.log
redirect_stderr=true

[program:server]
command=$WRAPPERS/server.sh
autostart=true
autorestart=true
startsecs=5
stdout_logfile=$WORKSPACE/logs/server.log
redirect_stderr=true

[program:client]
command=$WRAPPERS/client.sh
autostart=true
autorestart=true
startsecs=5
stdout_logfile=$WORKSPACE/logs/client.log
redirect_stderr=true
SUPCONF

# ── Stop any running instance then start fresh ────────────────────────────
if [ -S "$SOCK" ]; then
    supervisorctl -c "$CONF" shutdown 2>/dev/null || true
    sleep 3
fi

echo "==> Starting all services..."
supervisord -c "$CONF"
sleep 6

# ── Status ────────────────────────────────────────────────────────────────
supervisorctl -c "$CONF" status

# ── Shortcut alias ────────────────────────────────────────────────────────
ALIAS_LINE="alias ihctl='supervisorctl -c $CONF'"
grep -qF "alias ihctl" ~/.bashrc 2>/dev/null || echo "$ALIAS_LINE" >> ~/.bashrc
# Make alias available in current session
eval "$ALIAS_LINE" 2>/dev/null || true

# ── Done ──────────────────────────────────────────────────────────────────
POD_ID="${RUNPOD_POD_ID:-<pod-id>}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Application stack is up"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Client  → https://${POD_ID}-3000.proxy.runpod.net"
echo "  API     → https://${POD_ID}-7000.proxy.runpod.net"
echo "  AI      → https://${POD_ID}-8000.proxy.runpod.net"
echo "  MinIO   → https://${POD_ID}-9001.proxy.runpod.net"
echo ""
echo "  First boot? Pull Ollama models:"
echo "    ollama pull nomic-embed-text"
echo "    ollama pull llama3.1:8b"
echo "    ollama pull qwen3:32b"
echo ""
echo "  Manage services (ihctl = supervisorctl shortcut):"
echo "    ihctl status"
echo "    ihctl restart api"
echo "    ihctl tail -f api"
echo "    tail -f $WORKSPACE/logs/api.log"
echo ""
