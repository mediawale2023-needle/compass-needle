#!/usr/bin/env bash
# Starts the partner-channel demo: seeded backend + MP frontend (/partner) + Admin app.
# Uses an isolated SQLite database; does not read .env or touch your real data.
#
#   bash scripts/partner_demo.sh
#   API_PORT=8010 MP_PORT=3100 ADMIN_PORT=3101 bash scripts/partner_demo.sh   # if a port is taken
#
# Ctrl+C stops everything.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-venv/bin/python}"
API_PORT="${API_PORT:-8000}"
MP_PORT="${MP_PORT:-3000}"
ADMIN_PORT="${ADMIN_PORT:-3001}"

if [ "$MP_PORT" != "3000" ] || [ "$ADMIN_PORT" != "3001" ]; then
  echo "Note: the backend only allows CORS from localhost:3000 and :3001 by default in the demo."
  echo "      Custom frontend ports need ALLOWED_ORIGINS edited in scripts/partner_demo.py."
fi

for port in "$API_PORT" "$MP_PORT" "$ADMIN_PORT"; do
  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop that process or set API_PORT / MP_PORT / ADMIN_PORT." >&2
    exit 1
  fi
done

trap 'echo; echo "Stopping demo..."; kill 0 2>/dev/null || true' EXIT INT TERM

"$PY" scripts/partner_demo.py --port "$API_PORT" &

printf "Waiting for the backend"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then echo " ready."; break; fi
  printf "."; sleep 1
done

# Process env wins over .env.local, so these frontends talk to the demo backend, not your real one.
(cd frontend && NEXT_PUBLIC_API_URL="http://localhost:${API_PORT}" npx next dev --port "$MP_PORT") &
(cd admin    && NEXT_PUBLIC_API_URL="http://localhost:${API_PORT}" npx next dev --port "$ADMIN_PORT") &

wait
