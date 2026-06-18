#!/usr/bin/env bash
#
# Start of.by behind CWP via Gunicorn.

set -euo pipefail

APP_DIR="/home/django/webapps/ofby"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"
RUN_DIR="$APP_DIR/run"
ENV_FILE="$APP_DIR/.env"

mkdir -p "$LOG_DIR" "$RUN_DIR"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings_prod}

exec "$VENV_DIR/bin/gunicorn" \
  --name ofby \
  --workers "${GUNICORN_WORKERS:-4}" \
  --bind "${GUNICORN_BIND:-127.0.0.1:8021}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --log-level "${GUNICORN_LOG_LEVEL:-info}" \
  --access-logfile "$LOG_DIR/gunicorn.access.log" \
  --error-logfile "$LOG_DIR/gunicorn.error.log" \
  --pid "$RUN_DIR/gunicorn.pid" \
  config.wsgi:application
