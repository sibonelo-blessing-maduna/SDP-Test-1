#!/usr/bin/env bash
# Development mode: FastAPI with hot reload on :8000 + Vite dev server on :5173
# (Vite proxies /api to the real backend). Ctrl-C stops both.
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY=python3; fi

pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup INT TERM

(cd backend && exec "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
pids+=($!)
(cd frontend && exec env VITE_PROXY_TARGET=http://127.0.0.1:8000 npm run dev) &
pids+=($!)

echo "API  : http://127.0.0.1:8000  (docs at /docs)"
echo "Vite : http://127.0.0.1:5173  (proxies /api to the API)"
wait
