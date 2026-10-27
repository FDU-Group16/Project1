#!/bin/sh
set -eu
if [ "${APP_MODULE:-}" = "services.m3.main:app" ] && [ -n "${M3_DATABASE_URL:-}" ]; then
  python -m services.m3.migrate
fi
exec uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$PORT"
