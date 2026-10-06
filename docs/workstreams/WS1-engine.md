# WS1 — Metric Engine (critical path)

**Branch:** `feat/ws1-engine` · **Owns:** `backend/rat_engine/**` · **Owner:** integration lead

## Mission
Turn a git repository into the SQLite store (Contract B) and export metrics (Contract A) that
reproduce the reference CSVs **exactly** for cJSON → redis → git.

## Pinned semantics (empirically verified — do not "improve" these)
1. `git rev-list --no-merges <ref>` = H̄; `commit_count` = |H̄| including commits with no changes.
2. Single streaming pass: `git log --no-merges --numstat -z -M50% --format='<sentinel>%H<us>%ct<us>%aN <%aE><us>%s' <ref>`.
   **Never path-filter** (history simplification silently drops commits).
3. Attribute every entry verbatim to its path; nonzero renames → **new path**; `0/0` pure renames → touch markers on **both** old and new paths; skip binaries (`-`).
4. Author = `%aN <%aE>` mailmap-canonical (the reference oracle is mailmap-aware); dates = `%ct`; user-level merging stays a read-time overlay (Contract B).
5. Materialise per-commit directory rollups incl. root `/` (needed for exact `modifications` counts).
6. `modifications` counts commits with λ>0; 0/0 entries (pure renames) create an all-zero ALL row but no author rows (author rows need churn > 0).
7. Floats exported with Python `repr()`; rates use multiply-by-reciprocal `x * (1/|H|)` — direct division is 1 ulp off.

## Deliverables
- `scan` (streaming parser → SQLite, progress logging, idempotent), `metrics` query layer, `export` CLI.
- Performance: git.git (61k commits) must ingest within a few minutes and queries stay sub-second.

## Acceptance
`tools/rat_validate.py repo-references/cJSON_6d9f2443ab07.csv <(rat_engine export ...)` → exact match;
then redis and git. Keep a `--rename-mode` switch only if needed for debugging.

## Debugging notes (already learned the hard way)
- `git log -- <path>` and `git diff-tree -- <path>` defeat rename pairing & drop commits — don't use for scanning.
- `-z` rename entry = `a\td\t<EMPTY>` followed by two NUL-separated path chunks.
- Reference generator counted real `247  0  README` lines from branch commits — trust the stream, not assumptions about "the rename commit".
