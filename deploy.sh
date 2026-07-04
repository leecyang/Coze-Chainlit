#!/usr/bin/env bash

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
SERVICE_NAME="${SERVICE_NAME:-lingxi-backend}"
HOST="${1:-localhost}"
PORT="${LINGXI_PORT:-8123}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo ".env is missing. Create it from .env.example and fill required values."
  exit 1
fi

mkdir -p backend/data

docker compose -f "$COMPOSE_FILE" build "$SERVICE_NAME"
docker compose -f "$COMPOSE_FILE" up -d "$SERVICE_NAME"

echo "LingXi Chat is starting at http://$HOST:$PORT"
echo "Use: docker compose logs -f $SERVICE_NAME"
