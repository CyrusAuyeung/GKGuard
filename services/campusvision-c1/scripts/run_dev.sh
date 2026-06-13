#!/usr/bin/env bash
set -euo pipefail

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"

python -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
