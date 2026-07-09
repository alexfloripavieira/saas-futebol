#!/bin/sh
set -e

python src/manage.py migrate --noinput
python src/manage.py collectstatic --noinput --clear
exec "$@"
