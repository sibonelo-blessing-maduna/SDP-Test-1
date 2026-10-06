#!/usr/bin/env bash
# Full correctness gate (S3): engine vs the three reference CSVs + the complete
# test suite (engine edge cases, mutation detection, validator, API).
# Usage: bash scripts/verify.sh [repo ...]     (default: cjson redis git)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY=python3; fi

status=0
echo "=== 1/2 engine vs reference CSVs (byte-exact) =========================="
bash tools/validate_all.sh "$@" || status=1

echo
echo "=== 2/2 test suites ===================================================="
"$PY" -m pytest tests backend/tests -q || status=1

echo
if [ "$status" -eq 0 ]; then echo "VERIFY: PASS"; else echo "VERIFY: FAIL"; fi
exit "$status"
