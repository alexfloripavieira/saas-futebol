#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Uso: restore_postgres.sh /backups/arquivo.dump" >&2
  exit 2
fi

backup="$1"
if [ ! -f "$backup" ]; then
  echo "Backup não encontrado: $backup" >&2
  exit 2
fi

if [ -f "${backup}.sha256" ]; then
  sha256sum -c "${backup}.sha256"
fi

PGPASSWORD="$DB_PASSWORD" pg_restore \
  --host="${DB_HOST:-db}" \
  --port="${DB_PORT:-5432}" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  --clean \
  --if-exists \
  --no-owner \
  "$backup"

echo "Restauração concluída: $backup"
