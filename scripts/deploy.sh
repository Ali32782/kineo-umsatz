#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "→ .env nicht gefunden, kopiere .env.example"
  cp .env.example .env
  echo "  Bitte SECRET_KEY in .env anpassen!"
fi

echo "→ Docker Images bauen…"
docker compose build

echo "→ Container starten…"
docker compose up -d

echo ""
echo "✓ Kineo App läuft:"
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  Health:    http://localhost:8000/api/health"
echo ""
echo "Logs: docker compose logs -f"
