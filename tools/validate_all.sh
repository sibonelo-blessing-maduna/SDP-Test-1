#!/usr/bin/env bash
# Validate the metric engine against all three reference CSVs (scan -> export -> diff),
# then regenerate fixtures/mock. Usage: bash tools/validate_all.sh [repo ...]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/backend"

declare -A REF NAME DIR SHA
REF[cjson]="cJSON_6d9f2443ab07.csv"; NAME[cjson]="cJSON"; DIR[cjson]="cJSON"; SHA[cjson]="6d9f2443ab071f86e5d9b43025a40929ec41c46c"
REF[redis]="redis_b540ca49cba8.csv"; NAME[redis]="redis"; DIR[redis]="redis"; SHA[redis]="b540ca49cba815f3fbe634363c3df68d4f4f127a"
REF[git]="git_5a7d1e8045ce.csv";     NAME[git]="git";     DIR[git]="git";     SHA[git]="5a7d1e8045ce66c908f62598e26cbb8df7b39a90"

repos=("$@"); [ ${#repos[@]} -eq 0 ] && repos=(cjson redis git)
overall=0
for r in "${repos[@]}"; do
  echo "=== $r ==================================================="
  if [ ! -d "data/repos/${DIR[$r]}/.git" ]; then
    echo "SKIP: data/repos/${DIR[$r]} is not cloned"; overall=1; continue
  fi
  mkdir -p data/db
  python3 -m rat_engine scan --repo "data/repos/${DIR[$r]}" --name "${NAME[$r]}" \
      --db "data/db/$r.sqlite" --ref "${SHA[$r]}" || { echo "SCAN FAILED"; overall=1; continue; }
  python3 -m rat_engine export --db "data/db/$r.sqlite" --out "/tmp/${r}_produced.csv" || { echo "EXPORT FAILED"; overall=1; continue; }
  python3 tools/rat_validate.py "repo-references/${REF[$r]}" "/tmp/${r}_produced.csv" | tail -6
  if python3 tools/rat_validate.py "repo-references/${REF[$r]}" "/tmp/${r}_produced.csv" | grep -q "EXACT MATCH"; then
    echo "RESULT[$r]: PASS"
  else
    echo "RESULT[$r]: FAIL"; overall=1
  fi
done

echo "=== fixtures ==============================================="
python3 tools/make_fixtures.py || overall=1
[ $overall -eq 0 ] && echo "ALL VALIDATION DONE: PASS" || echo "ALL VALIDATION DONE: FAIL"
exit $overall
