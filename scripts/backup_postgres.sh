#!/bin/sh
set -eu

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${BACKUP_DIR:-/backups}"
output="${backup_dir}/${DB_NAME}_${timestamp}.dump"

mkdir -p "$backup_dir"
PGPASSWORD="$DB_PASSWORD" pg_dump \
  --host="${DB_HOST:-db}" \
  --port="${DB_PORT:-5432}" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  --format=custom \
  --no-owner \
  --file="$output"

sha256sum "$output" > "${output}.sha256"
echo "Backup criado: $output"
