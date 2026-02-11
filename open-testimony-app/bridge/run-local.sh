#!/usr/bin/env bash
# Run the bridge service natively on macOS with MPS GPU acceleration.
#
# Prerequisites:
#   - Python 3.11+
#   - Docker services running with: docker compose -f docker-compose.yml -f docker-compose.local-bridge.yml up -d
#
# This script:
#   1. Creates a Python venv (if needed) and installs dependencies
#   2. Creates local data directories for temp files and thumbnails
#   3. Sets environment variables pointing to localhost services
#   4. Starts uvicorn on port 8003 with DEVICE=mps

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
DATA_DIR="$SCRIPT_DIR/../data"

# --- Create venv and install deps if needed ---
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment..."
    python3.12 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if [ ! -f "$VENV_DIR/.deps-installed" ]; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
    touch "$VENV_DIR/.deps-installed"
fi

# --- Create local data directories ---
mkdir -p "$DATA_DIR/temp" "$DATA_DIR/thumbnails"

# --- Environment variables ---
# Database and MinIO on localhost (exposed by Docker)
export DATABASE_URL="postgresql://user:pass@localhost:5432/opentestimony"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="admin"
export MINIO_SECRET_KEY="supersecret"
export MINIO_BUCKET="opentestimony-videos"
export JWT_SECRET_KEY="change-me-in-production-use-a-real-secret"

# Model configuration
export VISION_MODEL_FAMILY="open_clip"
export VISION_MODEL_NAME="ViT-bigG-14"
export VISION_MODEL_PRETRAINED="laion2b_s39b_b160k"
export VISION_EMBEDDING_DIM="1280"
export TRANSCRIPT_MODEL_NAME="Qwen/Qwen3-Embedding-8B"
export TRANSCRIPT_EMBEDDING_DIM="4096"
export WHISPER_MODEL="large-v3"

# MPS GPU acceleration on Apple Silicon
export DEVICE="mps"
export USE_FP16="false"

# Processing
export FRAME_INTERVAL_SEC="2.0"
export BATCH_SIZE="16"
export WORKER_POLL_INTERVAL="10"
export TEMP_DIR="$DATA_DIR/temp"
export THUMBNAIL_DIR="$DATA_DIR/thumbnails"
export OT_API_URL="http://localhost:18080/api"

echo ""
echo "=== Bridge Local Mode ==="
echo "  Device:      $DEVICE"
echo "  Database:    $DATABASE_URL"
echo "  MinIO:       $MINIO_ENDPOINT"
echo "  Temp dir:    $TEMP_DIR"
echo "  Thumbnails:  $THUMBNAIL_DIR"
echo "  API URL:     $OT_API_URL"
echo ""

# --- Start the bridge ---
cd "$SCRIPT_DIR"
exec uvicorn main:app --host 0.0.0.0 --port 8003 --reload
