#!/bin/sh
set -eu

# Render-safe startup: never block the web service while large Ollama models download.
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/data/ollama}"
export PORT="${PORT:-10000}"
mkdir -p /data/ollama /data/projects

# Start Ollama locally.
ollama serve >/tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

# Wait only for the Ollama HTTP service, not for model downloads.
READY=0
for i in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "[Aethel] Ollama did not become ready. Showing log:"
  tail -n 80 /tmp/ollama.log || true
  exit 1
fi

MODEL="${AETHEL_OLLAMA_MODEL:-qwen2.5:3b-instruct-q4_K_M}"
VISION_MODEL="${AETHEL_VISION_MODEL:-qwen2.5vl:3b}"
export AETHEL_OLLAMA_MODEL="$MODEL"
export AETHEL_VISION_MODEL="$VISION_MODEL"
export AETHEL_OLLAMA_URL="http://127.0.0.1:11434"

# Start Aethel immediately so Render can pass its health check.
python app.py &
APP_PID=$!

# Download models in the background. A slow/failed model download must NOT
# prevent the website itself from coming online.
(
  echo "[Aethel] Checking main model: $MODEL"
  if ! curl -fsS http://127.0.0.1:11434/api/tags | grep -q '"name": "'"$MODEL"'"'; then
    echo "[Aethel] Downloading main model in background: $MODEL"
    ollama pull "$MODEL" || echo "[Aethel] Main model download failed; retry later."
  fi
  echo "[Aethel] Checking vision model: $VISION_MODEL"
  if ! curl -fsS http://127.0.0.1:11434/api/tags | grep -q '"name": "'"$VISION_MODEL"'"'; then
    echo "[Aethel] Downloading vision model in background: $VISION_MODEL"
    ollama pull "$VISION_MODEL" || echo "[Aethel] Vision model download failed; retry later."
  fi
  echo "[Aethel] Model bootstrap finished."
) >/tmp/aethel-model-bootstrap.log 2>&1 &
BOOTSTRAP_PID=$!

echo "[Aethel] Web server running on 0.0.0.0:${PORT}"
echo "[Aethel] Ollama: ${OLLAMA_HOST}"
echo "[Aethel] Model bootstrap running in background (PID ${BOOTSTRAP_PID})."

cleanup() {
  kill "$BOOTSTRAP_PID" 2>/dev/null || true
  kill "$APP_PID" 2>/dev/null || true
  kill "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

wait "$APP_PID"
