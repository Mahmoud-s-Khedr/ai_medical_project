#!/usr/bin/env sh
set -eu

cd /app

python manage.py migrate --noinput
python manage.py import_medicines --path medicines.csv
python manage.py seed_demo_data --profile "${SEED_PROFILE:-large}" --password "${SEED_PASSWORD:-StrongPass123!}"

exec gunicorn medicine_backend.wsgi:application \
  --bind 0.0.0.0:8000 \
  --worker-class "${GUNICORN_WORKER_CLASS:-gthread}" \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-300}" \
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-60}" \
  --keep-alive "${GUNICORN_KEEPALIVE:-5}" \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}"
