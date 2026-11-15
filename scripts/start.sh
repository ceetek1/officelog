#!/bin/sh
# Container start: update the database, then serve. Railway sets $PORT.
set -e
python -m app.admin migrate
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
