#!/usr/bin/env bash
set -euo pipefail

# URIP Postgres backup
# - Daily gzip-compressed pg_dump to /var/backups
# - Retain 14 days
# - Optional S3 upload when S3_BACKUP_BUCKET is set

BACKUP_DIR="${BACKUP_DIR:-/var/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATE_STR="$(date +%F)"
OUT_FILE="${BACKUP_DIR}/urip-pg-${DATE_STR}.sql.gz"

# Prefer the sync URL (psycopg / pg_dump format). Fallback to the dev default.
DB_URL="${DATABASE_URL_SYNC:-${DATABASE_URL:-postgresql://urip:urip_dev@localhost:5432/urip}}"

mkdir -p "${BACKUP_DIR}"

# Gemini LOW finding (AUDIT_GEMINI_TRI_A.md:22) — only prune old backups after
# confirming the new dump succeeded AND the output file is non-zero.
# Previously the find/delete ran unconditionally, risking a wipe of all backups
# when pg_dump silently failed (e.g., auth error, disk-full mid-write).
#
# Note: `set -o pipefail` causes the shell to exit immediately if any pipe
# command fails, so we disable it temporarily around the pipeline and capture
# the exit code manually, then re-enable it.
set +e +o pipefail
pg_dump --dbname="${DB_URL}" | gzip -c > "${OUT_FILE}"
DUMP_EXIT="${PIPESTATUS[0]}"
set -eo pipefail

if [ "${DUMP_EXIT}" -eq 0 ] && [ -s "${OUT_FILE}" ]; then
  # Delete backups older than retention window without using rm (INV-0).
  find "${BACKUP_DIR}" -type f -name "urip-pg-*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete
else
  echo "[backup] FAIL: pg_dump exit=${DUMP_EXIT} or output file empty; aborting cleanup — keeping old backups" >&2
  exit 1
fi

if [[ -n "${S3_BACKUP_BUCKET:-}" ]]; then
  if command -v aws >/dev/null 2>&1; then
    aws s3 cp "${OUT_FILE}" "s3://${S3_BACKUP_BUCKET}/$(basename "${OUT_FILE}")"
  else
    echo "S3_BACKUP_BUCKET set but aws CLI not found; skipping upload." >&2
  fi
fi

echo "Backup written: ${OUT_FILE}"
