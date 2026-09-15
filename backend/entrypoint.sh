#!/bin/sh
set -e

# Prod uses Alembic for schema; dev/compose sets SHORTY_AUTO_CREATE_TABLES=true
# (the default) and skips migrations, letting the app create tables on startup.
if [ "$SHORTY_AUTO_CREATE_TABLES" = "false" ]; then
  echo ">> running alembic upgrade head"
  alembic upgrade head
fi

# Cloud Run injects PORT (default 8080). Bind to it directly.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
