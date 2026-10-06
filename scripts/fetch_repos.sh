#!/usr/bin/env bash
# Clone the three pinned reference repositories into data/repos/ (deep clones)
# at the exact SHAs used by repo-references/*.csv, so the metrics can be
# regenerated and compared. Usage: bash scripts/fetch_repos.sh
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p data/repos

clone_at() { # url dir sha
  local url="$1" dir="$2" sha="$3"
  if [ -d "data/repos/$dir/.git" ]; then
    echo "skip: data/repos/$dir already cloned"
  else
    echo "cloning $url -> data/repos/$dir (full history; git.git is the big one)"
    git clone --quiet "$url" "data/repos/$dir"
  fi
  if ! git -C "data/repos/$dir" cat-file -e "$sha^{commit}" 2>/dev/null; then
    echo "ERROR: commit $sha not present in data/repos/$dir" >&2
    exit 1
  fi
  git -C "data/repos/$dir" checkout --quiet "$sha"
  echo "ok: $dir @ $sha"
}

clone_at https://github.com/DaveGamble/cJSON.git cJSON 6d9f2443ab071f86e5d9b43025a40929ec41c46c
clone_at https://github.com/redis/redis.git       redis b540ca49cba815f3fbe634363c3df68d4f4f127a
clone_at https://github.com/git/git.git           git   5a7d1e8045ce66c908f62598e26cbb8df7b39a90

echo "done — data/repos/{cJSON,redis,git} ready at the pinned SHAs"
