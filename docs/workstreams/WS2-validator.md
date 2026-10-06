# WS2 — Validator / QA harness

**Branch:** `feat/ws2-validator` · **Owns:** `tools/**`, `fixtures/**`, `tests/**`

## Mission
Give every other workstream an automated oracle. Never block on WS1: your tool consumes CSV files, period.

## Deliverables
1. `tools/rat_validate.py` (seed exists — extend it):
   - diff two metric CSVs (reference vs produced) matching on `(object_type, path, author)`
   - report: missing keys, extra keys, value mismatches (first 50 + counts), per-object-type summary
   - flags: `--tol` (abs tolerance for floats, default 0 = exact), `--ignore-paths`, `--json out.json`
   - exit 1 on any difference. Must detect every single-cell mutation injected into a copy of a reference file (write a test that proves it).
2. `tools/make_fixtures.py` (seed exists — extend it): regenerates `fixtures/mock/*.json` (Contract C shapes from the reference CSVs; commits/series from `data/repos/cJSON` when present, else flags synthetic data in `fixtures/mock/README.md`).
3. `tests/fixture_repo.py`: builds a **tiny deterministic git repo** (scripted commits with odd cases: rename+edit, delete, binary file, unicode author, merge commit) + zips it → `fixtures/tiny_repo.zip` for WS3 ingestion tests and WS1 edge tests. Keep SHA-free (dates/authors fixed via env).
4. `tools/bench.py`: times `rat_engine scan` + `export` on a given repo, prints commit-parsing throughput; used at S3 against git.git.

## Acceptance
- `pytest tests/ -q` green; mutation-detection test demonstrates 100% detection.
- Fixtures regenerate byte-stable (idempotent runs, sorted keys).
