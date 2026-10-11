#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
command -v docker >/dev/null 2>&1 || { echo 'Install Docker Engine and Docker Compose first.' >&2; exit 1; }
docker compose version >/dev/null
umask 077
[ -f .env ] || cp .env.example .env
mkdir -p .secrets
if [ ! -s .secrets/admin-password ]; then
  docker run --rm python:3.12-slim-bookworm python -c 'import secrets; print(secrets.token_urlsafe(24))' > .secrets/admin-password
fi
docker compose up -d --build
echo 'Cadence is starting: http://localhost:8787'
echo 'Administrator: CADENCE_ADMIN_USER from .env (default admin)'
echo 'Password: .secrets/admin-password (generated locally; never committed)'
echo 'Next: complete Emby setup, then docker compose run --rm cadence python configure.py'
