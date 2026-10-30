#!/bin/sh
set -eu
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo 'Install Docker and Docker Compose first.'; exit 1; }
[ -f .env ] || cp .env.example .env
docker info >/dev/null
docker compose up --build -d
echo 'CHINNU is starting at http://localhost:8080 (or APP_PORT from .env).'
