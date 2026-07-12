#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Uso: restore_media.sh /backups/media_AAAAMMDDTHHMMSSZ.tar.gz" >&2
  exit 2
fi
backup="$1"
media_dir="${MEDIA_DIR:-/media}"
test -f "$backup" || { echo "Backup não encontrado: $backup" >&2; exit 2; }
if [ -f "${backup}.sha256" ]; then
  sha256sum -c "${backup}.sha256"
fi
mkdir -p "$media_dir"
tar -C "$media_dir" -xzf "$backup"
echo "Restauração de mídia concluída: $backup"
