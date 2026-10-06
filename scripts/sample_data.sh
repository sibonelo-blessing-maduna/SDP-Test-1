#!/usr/bin/env bash
# Scan the three pinned repositories into data/db/<id>.sqlite and register them
# in data/catalog.json so the API and UI serve them immediately.
# Run scripts/fetch_repos.sh first (or upload your own repo through the UI).
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY=python3; fi
export PYTHONPATH="$ROOT/backend"
mkdir -p data/db

scan_repo() { # id name dir sha
  local id="$1" name="$2" dir="$3" sha="$4"
  if [ ! -d "data/repos/$dir/.git" ]; then
    echo "SKIP $id: data/repos/$dir not cloned — run scripts/fetch_repos.sh"
    return 0
  fi
  echo "=== scanning $id ($name @ ${sha:0:12})"
  "$PY" -m rat_engine scan --repo "data/repos/$dir" --name "$name" \
      --db "data/db/$id.sqlite" --ref "$sha"
}

scan_repo cjson cJSON cJSON 6d9f2443ab071f86e5d9b43025a40929ec41c46c
scan_repo redis redis redis b540ca49cba815f3fbe634363c3df68d4f4f127a
scan_repo git   git   git   5a7d1e8045ce66c908f62598e26cbb8df7b39a90

"$PY" - <<'EOF'
import sys
from pathlib import Path

sys.path.insert(0, "backend")
from app import catalog  # noqa: E402

root = Path.cwd()
meta = {
    "cjson": ("cJSON", "https://github.com/DaveGamble/cJSON.git",
              "6d9f2443ab071f86e5d9b43025a40929ec41c46c", 955),
    "redis": ("redis", "https://github.com/redis/redis.git",
              "b540ca49cba815f3fbe634363c3df68d4f4f127a", 11874),
    "git": ("git", "https://github.com/git/git.git",
            "5a7d1e8045ce66c908f62598e26cbb8df7b39a90", 61101),
}
for rid, (name, url, sha, n) in meta.items():
    db = root / "data" / "db" / f"{rid}.sqlite"
    if not db.exists():
        print(f"no db for {rid} — skipped")
        continue
    catalog.upsert({
        "id": rid, "name": name, "source": "url:" + url, "ref_sha": sha,
        "commit_count": n, "status": "ready", "progress": 1.0, "db_path": str(db),
    })
    print(f"registered {rid} ({n} commits)")
EOF

echo "sample data ready — start the app with scripts/serve.sh"
