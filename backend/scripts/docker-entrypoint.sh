#!/bin/sh
# backend/scripts/docker-entrypoint.sh — migrate, then serve (Slice 4).
set -eu
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
