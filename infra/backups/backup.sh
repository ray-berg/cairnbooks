#!/usr/bin/env bash
# =============================================================================
# CairnBooks — Nightly Backup Script
#
# Performs a pg_dump of the CairnBooks PostgreSQL database, compresses it,
# rotates old local copies, and syncs the latest backup to MinIO (local) and
# optionally to a remote S3-compatible endpoint for off-LXC storage.
#
# Usage (manual):
#   sudo bash /opt/cairnbooks/infra/backups/backup.sh
#
# Scheduled via systemd timer (see cairnbooks-backup.timer) or cron.
#
# Configuration — copy backup.env.example to backup.env and fill in values:
#   /opt/cairnbooks/infra/backups/backup.env
#
# Exit codes:
#   0  success
#   1  pg_dump failed
#   2  MinIO upload failed (local)
#   3  remote sync failed (non-fatal by default; see REMOTE_FAIL_FATAL)
# =============================================================================
set -euo pipefail

# ── Load environment ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${CAIRNBOOKS_ENV:-${SCRIPT_DIR}/backup.env}"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

# ── Configuration (overridable via environment or backup.env) ─────────────────

# Where CairnBooks is deployed
APP_DIR="${APP_DIR:-/opt/cairnbooks}"

# Docker compose project (used to find the postgres container)
COMPOSE_PROJECT="${COMPOSE_PROJECT:-cairnbooks}"

# PostgreSQL connection settings (matched to docker-compose.yml defaults)
PG_USER="${PG_USER:-cairnbooks}"
PG_DB="${PG_DB:-cairnbooks}"
PG_PASSWORD="${PG_PASSWORD:-cairnbooks}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"

# Local backup retention (days)
RETAIN_DAYS="${RETAIN_DAYS:-7}"

# Local backup directory (inside the LXC)
BACKUP_DIR="${BACKUP_DIR:-/var/backups/cairnbooks}"

# MinIO (local service) settings
MINIO_ALIAS="${MINIO_ALIAS:-cairnbooks-local}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-cairnbooks}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-cairnbooks_secret}"
MINIO_BUCKET="${MINIO_BUCKET:-cairnbooks-backups}"

# Remote (off-LXC) S3/MinIO settings — leave REMOTE_ENDPOINT empty to skip
REMOTE_ALIAS="${REMOTE_ALIAS:-cairnbooks-remote}"
REMOTE_ENDPOINT="${REMOTE_ENDPOINT:-}"          # e.g. https://s3.example.com
REMOTE_ACCESS_KEY="${REMOTE_ACCESS_KEY:-}"
REMOTE_SECRET_KEY="${REMOTE_SECRET_KEY:-}"
REMOTE_BUCKET="${REMOTE_BUCKET:-cairnbooks-backups}"
# Set to "true" to make the script fail if remote sync fails
REMOTE_FAIL_FATAL="${REMOTE_FAIL_FATAL:-false}"

# ── Helpers ───────────────────────────────────────────────────────────────────
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/cairnbooks_${TIMESTAMP}.sql.gz"
LOG_PREFIX="[cairnbooks-backup ${TIMESTAMP}]"

log()  { echo "${LOG_PREFIX} $*"; }
die()  { echo "${LOG_PREFIX} ERROR: $*" >&2; exit "${2:-1}"; }
warn() { echo "${LOG_PREFIX} WARN: $*" >&2; }

# ── Pre-flight ────────────────────────────────────────────────────────────────
log "Starting backup"
mkdir -p "${BACKUP_DIR}"

# Determine whether we run pg_dump via docker exec or directly
if command -v docker &>/dev/null; then
  # Find the running postgres container for this compose project
  PG_CONTAINER="$(docker ps --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
                             --filter "name=postgres" \
                             --format '{{.Names}}' | head -1)"
fi

# ── pg_dump ───────────────────────────────────────────────────────────────────
log "Running pg_dump → ${BACKUP_FILE}"

if [[ -n "${PG_CONTAINER:-}" ]]; then
  log "  via docker exec on container: ${PG_CONTAINER}"
  docker exec -e PGPASSWORD="${PG_PASSWORD}" "${PG_CONTAINER}" \
    pg_dump -U "${PG_USER}" -d "${PG_DB}" --no-password \
    | gzip > "${BACKUP_FILE}" \
    || die "pg_dump (docker) failed" 1
else
  log "  via direct psql connection (${PG_HOST}:${PG_PORT})"
  PGPASSWORD="${PG_PASSWORD}" pg_dump \
    -h "${PG_HOST}" -p "${PG_PORT}" \
    -U "${PG_USER}" -d "${PG_DB}" \
    | gzip > "${BACKUP_FILE}" \
    || die "pg_dump (direct) failed" 1
fi

BACKUP_SIZE="$(du -sh "${BACKUP_FILE}" | cut -f1)"
log "pg_dump complete — ${BACKUP_SIZE} written to ${BACKUP_FILE}"

# ── Local MinIO upload ────────────────────────────────────────────────────────
if command -v mc &>/dev/null; then
  log "Uploading to local MinIO (${MINIO_ENDPOINT}/${MINIO_BUCKET})"

  # Configure alias (idempotent)
  mc alias set "${MINIO_ALIAS}" \
    "${MINIO_ENDPOINT}" \
    "${MINIO_ACCESS_KEY}" \
    "${MINIO_SECRET_KEY}" \
    --api S3v4 &>/dev/null

  # Ensure bucket exists
  mc mb --ignore-existing "${MINIO_ALIAS}/${MINIO_BUCKET}" &>/dev/null

  # Upload
  mc cp "${BACKUP_FILE}" "${MINIO_ALIAS}/${MINIO_BUCKET}/" \
    || die "MinIO local upload failed" 2

  log "MinIO upload complete → ${MINIO_ALIAS}/${MINIO_BUCKET}/$(basename "${BACKUP_FILE}")"
else
  warn "mc (MinIO client) not found — skipping local MinIO upload"
fi

# ── Remote (off-LXC) sync ─────────────────────────────────────────────────────
if [[ -n "${REMOTE_ENDPOINT}" ]] && command -v mc &>/dev/null; then
  log "Syncing to remote endpoint (${REMOTE_ENDPOINT}/${REMOTE_BUCKET})"

  mc alias set "${REMOTE_ALIAS}" \
    "${REMOTE_ENDPOINT}" \
    "${REMOTE_ACCESS_KEY}" \
    "${REMOTE_SECRET_KEY}" \
    --api S3v4 &>/dev/null

  mc mb --ignore-existing "${REMOTE_ALIAS}/${REMOTE_BUCKET}" &>/dev/null

  if mc cp "${BACKUP_FILE}" "${REMOTE_ALIAS}/${REMOTE_BUCKET}/"; then
    log "Remote sync complete → ${REMOTE_ALIAS}/${REMOTE_BUCKET}/$(basename "${BACKUP_FILE}")"
  else
    if [[ "${REMOTE_FAIL_FATAL}" == "true" ]]; then
      die "Remote sync failed" 3
    else
      warn "Remote sync failed — backup is still stored locally and in local MinIO"
    fi
  fi
elif [[ -n "${REMOTE_ENDPOINT}" ]]; then
  warn "mc not found — skipping remote sync to ${REMOTE_ENDPOINT}"
else
  log "No REMOTE_ENDPOINT configured — skipping off-LXC sync"
fi

# ── Rotate old local backups ──────────────────────────────────────────────────
log "Rotating local backups older than ${RETAIN_DAYS} days in ${BACKUP_DIR}"
find "${BACKUP_DIR}" \
  -maxdepth 1 \
  -name "cairnbooks_*.sql.gz" \
  -mtime "+${RETAIN_DAYS}" \
  -delete \
  -print \
  | while IFS= read -r f; do log "  Deleted old backup: $(basename "${f}")"; done

REMAINING="$(find "${BACKUP_DIR}" -maxdepth 1 -name "cairnbooks_*.sql.gz" | wc -l)"
log "Backup rotation complete — ${REMAINING} backup(s) retained locally"

# ── Summary ───────────────────────────────────────────────────────────────────
log "Backup finished successfully"
log "  File : ${BACKUP_FILE} (${BACKUP_SIZE})"
log "  Local dir retained: ${REMAINING} file(s)"
