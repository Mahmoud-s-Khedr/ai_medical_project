#!/usr/bin/env sh
set -eu

cd /app

python manage.py migrate --noinput
python manage.py import_medicines --path medicines.csv
python manage.py seed_demo_data --profile "${SEED_PROFILE:-large}" --password "${SEED_PASSWORD:-StrongPass123!}"

exec gunicorn medicine_backend.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-120}"
