#!/bin/sh
set -eu

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${BACKUP_DIR:-/backups}"
media_dir="${MEDIA_DIR:-/media}"
output="${backup_dir}/media_${timestamp}.tar.gz"

mkdir -p "$backup_dir"
tar -C "$media_dir" -czf "$output" .
sha256sum "$output" > "${output}.sha256"
echo "Backup de mídia criado: $output"
