#!/usr/bin/env bash
#
# Деплой / обновление of.by на сервере CWP.
# Запускать от пользователя django:
#   cd /home/django/webapps/ofby && bash deploy/deploy.sh

set -euo pipefail

APP_DIR="/home/django/webapps/ofby"
VENV="$APP_DIR/venv"
ENV_FILE="$APP_DIR/.env"

cd "$APP_DIR"

echo "==> Загружаем переменные окружения..."
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

export DJANGO_SETTINGS_MODULE=config.settings_prod

echo "==> Устанавливаем/обновляем зависимости..."
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r requirements.txt

echo "==> Применяем миграции..."
"$VENV/bin/python" manage.py migrate --noinput

echo "==> Собираем статику..."
"$VENV/bin/python" manage.py collectstatic --noinput --clear

echo "==> Очищаем кэш Django..."
"$VENV/bin/python" manage.py shell -c \
  "from django.core.cache import cache; cache.clear(); print('Cache cleared')"

echo "==> Перезапускаем gunicorn..."
systemctl restart gunicorn-ofby

echo "==> Готово."
