# WS3 — Backend API (FastAPI)

**Branch:** `feat/ws3-api` · **Owns:** `backend/app/**`, `backend/requirements.txt`

## Mission
Serve Contract C endpoints. Ingest repositories (zip upload + deep clone), run WS1 scans in
background threads, expose metrics with all filters and author merging.

## Deliverables
1. FastAPI app (`backend/app/main.py`) serving `/api/*`; static-serve `frontend/dist` when built.
2. Ingestion (`backend/app/ingest.py`):
   - `POST /api/repos/upload` — accept zip, extract to `data/repos/<id>/`, validate `.git` inside, register; errors → 400 with clear detail (it *is* the usability rubric)
   - `POST /api/repos/clone` — `git clone` (full history, not shallow) in a worker thread; reject non-URLs
   - background scan via `rat_engine.scan`; progress into store `scan_log` + catalog
   - catalog: `data/catalog.json` (id → name/source/ref/status) — atomic writes
3. Metrics service implementing **Contract B query semantics** exactly (incl. read-time author-merge overlay `LEFT JOIN author_merges`, ownership, modification_frequency, churn_rate, |H| including unchanged commits).
4. Authors endpoints: list, merge, unmerge, mailmap dry-run + apply (canonicalise raw authors via `git check-mailmap` inside the repo).
5. `ARCH_MOCK=1` env → use in-memory fixture store so the API is testable without WS1 done (this is the S1 switch — flip to real store by removing the env var).
6. Error handling: 404 unknown repo, 409 scan-in-progress conflicts, 422 bad filters (from>to), friendly messages.

## Acceptance
- Contract tests (pytest + httpx) green against mock store, then re-run green against the real store after S1.
- Zip of `fixtures/tiny_repo.zip` ingests end-to-end; clone URL of cJSON ingests end-to-end.
