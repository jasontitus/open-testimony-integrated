#!/usr/bin/env bash
# =============================================================================
# Open Testimony — Backup Script
# Backs up PostgreSQL and MinIO data to a GCS bucket.
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated (gcloud auth login)
#   2. GCS bucket created (gsutil mb gs://your-backup-bucket)
#   3. mc (MinIO client) installed: https://min.io/docs/minio/linux/reference/minio-mc.html
#   4. mc alias configured: mc alias set ot http://localhost:9000 admin supersecret
#
# Usage:
#   ./scripts/backup.sh                    # Uses defaults
#   GCS_BUCKET=gs://my-bucket ./scripts/backup.sh
#
# Cron example (daily at 2am):
#   0 2 * * * /path/to/open-testimony-app/scripts/backup.sh >> /var/log/ot-backup.log 2>&1
# =============================================================================
set -euo pipefail

# --- Configuration (override via environment) ---
GCS_BUCKET="${GCS_BUCKET:-gs://opentestimony-backups}"
DB_CONTAINER="${DB_CONTAINER:-open-testimony-app-db-1}"
DB_USER="${DB_USER:-user}"
DB_NAME="${DB_NAME:-opentestimony}"
MINIO_ALIAS="${MINIO_ALIAS:-ot}"
MINIO_BUCKET="${MINIO_BUCKET:-opentestimony-videos}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/ot-backup-${TIMESTAMP}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

cleanup() { rm -rf "${BACKUP_DIR}"; }
trap cleanup EXIT

mkdir -p "${BACKUP_DIR}"

# --- 1. PostgreSQL Backup ---
log "Starting PostgreSQL backup..."
PGDUMP_FILE="${BACKUP_DIR}/opentestimony_${TIMESTAMP}.sql.gz"

docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" \
    | gzip > "${PGDUMP_FILE}"

PGDUMP_SIZE=$(du -h "${PGDUMP_FILE}" | cut -f1)
log "PostgreSQL dump: ${PGDUMP_SIZE} compressed"

# Upload to GCS
gsutil -q cp "${PGDUMP_FILE}" "${GCS_BUCKET}/postgres/${TIMESTAMP}.sql.gz"
log "PostgreSQL backup uploaded to ${GCS_BUCKET}/postgres/${TIMESTAMP}.sql.gz"

# --- 2. MinIO Backup (incremental mirror) ---
log "Starting MinIO mirror to GCS..."

# mc mirror is incremental — only copies new/changed objects
mc mirror --overwrite --remove "${MINIO_ALIAS}/${MINIO_BUCKET}" "${GCS_BUCKET}/minio/${MINIO_BUCKET}/" 2>&1 \
    | while IFS= read -r line; do log "  mc: ${line}"; done

log "MinIO mirror complete"

# --- 3. Prune old PostgreSQL backups ---
log "Pruning PostgreSQL backups older than ${RETENTION_DAYS} days..."
CUTOFF_DATE=$(date -v-${RETENTION_DAYS}d +%Y%m%d 2>/dev/null || date -d "${RETENTION_DAYS} days ago" +%Y%m%d)

gsutil ls "${GCS_BUCKET}/postgres/" 2>/dev/null | while read -r obj; do
    # Extract date from filename (YYYYMMDD_HHMMSS.sql.gz)
    basename=$(basename "${obj}")
    obj_date=$(echo "${basename}" | grep -oE '^[0-9]{8}' || true)
    if [[ -n "${obj_date}" && "${obj_date}" < "${CUTOFF_DATE}" ]]; then
        log "  Deleting old backup: ${basename}"
        gsutil -q rm "${obj}"
    fi
done

log "Backup complete."
