#!/usr/bin/env bash
# =============================================================================
# Open Testimony — Reindex Script
#
# Modes:
#   fix       — Fill in missing indexes only (default). Safe to run anytime.
#   visual    — Delete + regenerate visual embeddings only (after vision model change)
#   full      — Delete everything + regenerate all indexes from scratch
#
# Usage:
#   ./scripts/reindex.sh                     # Fix all videos (default)
#   ./scripts/reindex.sh fix                 # Same as above
#   ./scripts/reindex.sh fix <video-id>      # Fix one video
#   ./scripts/reindex.sh visual              # Visual-only reindex, all videos
#   ./scripts/reindex.sh visual <video-id>   # Visual-only reindex, one video
#   ./scripts/reindex.sh full                # Full reindex, all videos
#   ./scripts/reindex.sh full <video-id>     # Full reindex, one video
#
# Environment:
#   BASE_URL   — Base URL of the Open Testimony instance (default: http://localhost:18080)
#   USERNAME   — Admin username (default: admin)
#   PASSWORD   — Admin password (default: admin)
# =============================================================================
set -euo pipefail

MODE="${1:-fix}"
VIDEO_ID="${2:-}"

BASE_URL="${BASE_URL:-http://localhost:18080}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-admin}"

COOKIE_JAR=$(mktemp)
trap 'rm -f "${COOKIE_JAR}"' EXIT

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Validate mode
case "${MODE}" in
    fix|visual|full) ;;
    *)
        echo "Unknown mode: ${MODE}"
        echo "Usage: $0 [fix|visual|full] [video-id]"
        exit 1
        ;;
esac

# --- 1. Authenticate ---
log "Logging in as ${USERNAME}..."
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' \
    -X POST "${BASE_URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"${USERNAME}\", \"password\": \"${PASSWORD}\"}" \
    -c "${COOKIE_JAR}")

if [ "${HTTP_CODE}" != "200" ]; then
    log "ERROR: Login failed (HTTP ${HTTP_CODE})"
    exit 1
fi
log "Authenticated."

# --- 2. Check current status ---
log "Current indexing status:"
curl -s -b "${COOKIE_JAR}" "${BASE_URL}/ai-search/indexing/status" | python3 -m json.tool
echo

# --- 3. Build endpoint URL ---
case "${MODE}" in
    fix)
        if [ -n "${VIDEO_ID}" ]; then
            ENDPOINT="/ai-search/indexing/fix/${VIDEO_ID}"
            DESC="fix for video ${VIDEO_ID}"
        else
            ENDPOINT="/ai-search/indexing/fix-all"
            DESC="fix for ALL videos"
        fi
        ;;
    visual)
        if [ -n "${VIDEO_ID}" ]; then
            ENDPOINT="/ai-search/indexing/reindex-visual/${VIDEO_ID}"
            DESC="visual reindex for video ${VIDEO_ID}"
        else
            ENDPOINT="/ai-search/indexing/reindex-visual-all"
            DESC="visual reindex for ALL videos"
        fi
        ;;
    full)
        if [ -n "${VIDEO_ID}" ]; then
            ENDPOINT="/ai-search/indexing/reindex/${VIDEO_ID}"
            DESC="full reindex for video ${VIDEO_ID}"
        else
            ENDPOINT="/ai-search/indexing/reindex-all"
            DESC="full reindex for ALL videos"
        fi
        ;;
esac

# --- 4. Trigger reindex ---
log "Triggering ${DESC}..."
RESP=$(curl -s -w '\n%{http_code}' \
    -X POST "${BASE_URL}${ENDPOINT}" \
    -b "${COOKIE_JAR}")

HTTP_CODE=$(echo "${RESP}" | tail -1)
BODY=$(echo "${RESP}" | sed '$d')

if [ "${HTTP_CODE}" != "200" ]; then
    log "ERROR: Request failed (HTTP ${HTTP_CODE})"
    echo "${BODY}" | python3 -m json.tool 2>/dev/null || echo "${BODY}"
    exit 1
fi

echo "${BODY}" | python3 -m json.tool
log "Queued. Worker will process jobs in the background."

# --- 5. Poll status until done ---
log "Polling status every 10s (Ctrl-C to stop)..."
echo
while true; do
    STATUS=$(curl -s -b "${COOKIE_JAR}" "${BASE_URL}/ai-search/indexing/status")
    PENDING=$(echo "${STATUS}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('pending',0))")
    P_VISUAL=$(echo "${STATUS}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('pending_visual',0))")
    P_FIX=$(echo "${STATUS}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('pending_fix',0))")
    PROCESSING=$(echo "${STATUS}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('processing',0))")
    COMPLETED=$(echo "${STATUS}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('completed',0))")
    FAILED=$(echo "${STATUS}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('failed',0))")

    TOTAL_PENDING=$((PENDING + P_VISUAL + P_FIX))

    printf "\r  queued=%s  processing=%s  completed=%s  failed=%s    " \
        "${TOTAL_PENDING}" "${PROCESSING}" "${COMPLETED}" "${FAILED}"

    if [ "${TOTAL_PENDING}" = "0" ] && [ "${PROCESSING}" = "0" ]; then
        echo
        log "Done! All jobs completed."
        if [ "${FAILED}" != "0" ]; then
            log "WARNING: ${FAILED} job(s) failed. Check bridge logs for details."
        fi
        break
    fi

    sleep 10
done

# --- 6. Final health check ---
echo
log "Bridge health:"
curl -s -b "${COOKIE_JAR}" "${BASE_URL}/ai-search/health" | python3 -m json.tool
