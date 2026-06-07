#!/usr/bin/env bash
# =============================================================================
# CairnBooks — Database Restore Script
#
# Restores a CairnBooks PostgreSQL backup from a local file or directly from
# MinIO (local or remote).
#
# Usage:
#   # Restore from a local .sql.gz file
#   sudo bash infra/backups/restore.sh /var/backups/cairnbooks/cairnbooks_20240101_020000.sql.gz
#
#   # Restore the latest backup from local MinIO
#   sudo bash infra/backups/restore.sh --latest
#
#   # List available backups in MinIO then restore a specific one
#   sudo bash infra/backups/restore.sh --list
#   sudo bash infra/backups/restore.sh --from-minio cairnbooks_20240101_020000.sql.gz
#
# The script will:
#   1. Stop the backend service (to avoid writes during restore)
#   2. Drop and recreate the cairnbooks database
#   3. Restore the pg_dump archive
#   4. Restart the backend service
#
# See docs/deployment/backups.md for the full restore runbook.
# =============================================================================
set -euo pipefail

# ── Load environment ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${CAIRNBOOKS_ENV:-${SCRIPT_DIR}/backup.env}"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

# ── Configuration ─────────────────────────────────────────────────────────────
APP_DIR="${APP_DIR:-/opt/cairnbooks}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-cairnbooks}"
PG_USER="${PG_USER:-cairnbooks}"
PG_DB="${PG_DB:-cairnbooks}"
PG_PASSWORD="${PG_PASSWORD:-cairnbooks}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/cairnbooks}"
MINIO_ALIAS="${MINIO_ALIAS:-cairnbooks-local}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-cairnbooks}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-cairnbooks_secret}"
MINIO_BUCKET="${MINIO_BUCKET:-cairnbooks-backups}"
REMOTE_ALIAS="${REMOTE_ALIAS:-cairnbooks-remote}"
REMOTE_ENDPOINT="${REMOTE_ENDPOINT:-}"
REMOTE_ACCESS_KEY="${REMOTE_ACCESS_KEY:-}"
REMOTE_SECRET_KEY="${REMOTE_SECRET_KEY:-}"
REMOTE_BUCKET="${REMOTE_BUCKET:-cairnbooks-backups}"

# ── Helpers ───────────────────────────────────────────────────────────────────
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PREFIX="[cairnbooks-restore ${TIMESTAMP}]"

log()  { echo "${LOG_PREFIX} $*"; }
die()  { echo "${LOG_PREFIX} ERROR: $*" >&2; exit 1; }
warn() { echo "${LOG_PREFIX} WARN: $*" >&2; }

usage() {
  cat <<EOF
Usage: $0 [OPTION] [FILE]

Options:
  <file.sql.gz>          Restore from a local .sql.gz file
  --latest               Restore the most recent backup from local MinIO
  --from-minio <file>    Restore a named backup from local MinIO
  --from-remote <file>   Restore a named backup from the remote endpoint
  --list                 List available backups in local MinIO
  --list-remote          List available backups in the remote endpoint
  -h, --help             Show this help

Examples:
  $0 /var/backups/cairnbooks/cairnbooks_20240101_020000.sql.gz
  $0 --latest
  $0 --list
  $0 --from-minio cairnbooks_20240101_020000.sql.gz
EOF
  exit 0
}

# ── Parse arguments ───────────────────────────────────────────────────────────
MODE="file"
SOURCE_FILE=""

case "${1:-}" in
  "")          usage ;;
  -h|--help)   usage ;;
  --latest)    MODE="latest" ;;
  --list)      MODE="list" ;;
  --list-remote) MODE="list-remote" ;;
  --from-minio)
    MODE="from-minio"
    SOURCE_FILE="${2:-}"
    [[ -n "${SOURCE_FILE}" ]] || die "--from-minio requires a filename argument"
    ;;
  --from-remote)
    MODE="from-remote"
    SOURCE_FILE="${2:-}"
    [[ -n "${SOURCE_FILE}" ]] || die "--from-remote requires a filename argument"
    ;;
  -*)          die "Unknown option: $1 (try --help)" ;;
  *)           MODE="file"; SOURCE_FILE="$1" ;;
esac

# ── MinIO helpers ─────────────────────────────────────────────────────────────
ensure_mc() {
  command -v mc &>/dev/null || die "mc (MinIO client) is required but not installed. See docs/deployment/backups.md."
}

configure_local_alias() {
  mc alias set "${MINIO_ALIAS}" \
    "${MINIO_ENDPOINT}" \
    "${MINIO_ACCESS_KEY}" \
    "${MINIO_SECRET_KEY}" \
    --api S3v4 &>/dev/null
}

configure_remote_alias() {
  [[ -n "${REMOTE_ENDPOINT}" ]] || die "REMOTE_ENDPOINT is not configured in backup.env"
  mc alias set "${REMOTE_ALIAS}" \
    "${REMOTE_ENDPOINT}" \
    "${REMOTE_ACCESS_KEY}" \
    "${REMOTE_SECRET_KEY}" \
    --api S3v4 &>/dev/null
}

# ── List mode ─────────────────────────────────────────────────────────────────
if [[ "${MODE}" == "list" ]]; then
  ensure_mc
  configure_local_alias
  log "Available backups in local MinIO (${MINIO_BUCKET}):"
  mc ls "${MINIO_ALIAS}/${MINIO_BUCKET}/" | grep '\.sql\.gz$' | sort || warn "No backups found"
  exit 0
fi

if [[ "${MODE}" == "list-remote" ]]; then
  ensure_mc
  configure_remote_alias
  log "Available backups in remote MinIO (${REMOTE_BUCKET}):"
  mc ls "${REMOTE_ALIAS}/${REMOTE_BUCKET}/" | grep '\.sql\.gz$' | sort || warn "No backups found"
  exit 0
fi

# ── Download from MinIO ───────────────────────────────────────────────────────
if [[ "${MODE}" == "latest" ]]; then
  ensure_mc
  configure_local_alias
  log "Fetching latest backup from local MinIO"
  LATEST_NAME="$(mc ls "${MINIO_ALIAS}/${MINIO_BUCKET}/" 2>/dev/null \
    | grep '\.sql\.gz$' \
    | sort \
    | tail -1 \
    | awk '{print $NF}')"
  [[ -n "${LATEST_NAME}" ]] || die "No backups found in ${MINIO_ALIAS}/${MINIO_BUCKET}/"
  SOURCE_FILE="${BACKUP_DIR}/${LATEST_NAME}"
  log "Downloading ${LATEST_NAME} → ${SOURCE_FILE}"
  mkdir -p "${BACKUP_DIR}"
  mc cp "${MINIO_ALIAS}/${MINIO_BUCKET}/${LATEST_NAME}" "${SOURCE_FILE}"
fi

if [[ "${MODE}" == "from-minio" ]]; then
  ensure_mc
  configure_local_alias
  log "Downloading ${SOURCE_FILE} from local MinIO"
  DEST="${BACKUP_DIR}/${SOURCE_FILE}"
  mkdir -p "${BACKUP_DIR}"
  mc cp "${MINIO_ALIAS}/${MINIO_BUCKET}/${SOURCE_FILE}" "${DEST}"
  SOURCE_FILE="${DEST}"
fi

if [[ "${MODE}" == "from-remote" ]]; then
  ensure_mc
  configure_remote_alias
  log "Downloading ${SOURCE_FILE} from remote MinIO"
  DEST="${BACKUP_DIR}/${SOURCE_FILE}"
  mkdir -p "${BACKUP_DIR}"
  mc cp "${REMOTE_ALIAS}/${REMOTE_BUCKET}/${SOURCE_FILE}" "${DEST}"
  SOURCE_FILE="${DEST}"
fi

# ── Validate source file ──────────────────────────────────────────────────────
[[ -f "${SOURCE_FILE}" ]] || die "Backup file not found: ${SOURCE_FILE}"
log "Restoring from: ${SOURCE_FILE} ($(du -sh "${SOURCE_FILE}" | cut -f1))"

# ── Confirmation ──────────────────────────────────────────────────────────────
log ""
log "WARNING: This will DROP and recreate the '${PG_DB}' database."
log "         All current data will be PERMANENTLY DELETED."
log ""
if [[ "${CAIRNBOOKS_RESTORE_CONFIRM:-}" != "yes" ]]; then
  read -r -p "Type 'yes' to continue: " CONFIRM
  [[ "${CONFIRM}" == "yes" ]] || { log "Aborted."; exit 0; }
fi

# ── Stop backend ──────────────────────────────────────────────────────────────
PG_CONTAINER=""
BACKEND_RUNNING=false

if command -v docker &>/dev/null; then
  PG_CONTAINER="$(docker ps \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
    --filter "name=postgres" \
    --format '{{.Names}}' | head -1)"

  BACKEND_ID="$(docker ps \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
    --filter "name=backend" \
    --format '{{.ID}}' | head -1)"

  if [[ -n "${BACKEND_ID}" ]]; then
    BACKEND_RUNNING=true
    log "Stopping backend container (${BACKEND_ID})"
    docker stop "${BACKEND_ID}"
  fi
fi

# ── Drop and recreate DB ──────────────────────────────────────────────────────
log "Dropping database '${PG_DB}'"
if [[ -n "${PG_CONTAINER}" ]]; then
  docker exec -e PGPASSWORD="${PG_PASSWORD}" "${PG_CONTAINER}" \
    psql -U "${PG_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${PG_DB};"

  log "Recreating database '${PG_DB}'"
  docker exec -e PGPASSWORD="${PG_PASSWORD}" "${PG_CONTAINER}" \
    psql -U "${PG_USER}" -d postgres \
    -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"
else
  PGPASSWORD="${PG_PASSWORD}" psql \
    -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -d postgres \
    -c "DROP DATABASE IF EXISTS ${PG_DB};"

  PGPASSWORD="${PG_PASSWORD}" psql \
    -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -d postgres \
    -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"
fi

# ── Restore ───────────────────────────────────────────────────────────────────
log "Restoring pg_dump into '${PG_DB}'"
if [[ -n "${PG_CONTAINER}" ]]; then
  gunzip -c "${SOURCE_FILE}" \
    | docker exec -i -e PGPASSWORD="${PG_PASSWORD}" "${PG_CONTAINER}" \
        psql -U "${PG_USER}" -d "${PG_DB}" \
    || die "pg_restore failed"
else
  gunzip -c "${SOURCE_FILE}" \
    | PGPASSWORD="${PG_PASSWORD}" psql \
        -h "${PG_HOST}" -p "${PG_PORT}" \
        -U "${PG_USER}" -d "${PG_DB}" \
    || die "pg_restore failed"
fi

log "Database restore complete"

# ── Restart backend ───────────────────────────────────────────────────────────
if [[ "${BACKEND_RUNNING}" == "true" ]]; then
  log "Restarting backend"
  if [[ -f "${APP_DIR}/docker-compose.yml" ]]; then
    docker compose -f "${APP_DIR}/docker-compose.yml" start backend
  fi
fi

log "Restore finished successfully from: $(basename "${SOURCE_FILE}")"
