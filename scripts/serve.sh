#!/usr/bin/env bash
# One-command demo server: builds the frontend when needed, then serves the
# REST API and the SPA from FastAPI on http://localhost:8000.
# Usage: bash scripts/serve.sh [--build]     (HOST/PORT env overrides)
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY=python3; fi

if [ "${1:-}" = "--build" ] || [ ! -f frontend/dist/index.html ]; then
  echo "building frontend…"
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

echo "serving API + UI on http://${HOST:-127.0.0.1}:${PORT:-8000} (Ctrl-C to stop)"
cd backend
exec env HOST="${HOST:-127.0.0.1}" PORT="${PORT:-8000}" "$PY" -m app.main
