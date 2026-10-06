# WS5 — Infra / Docs / Demo

**Branch:** `chore/ws5-infra-docs` · **Owns:** `README.md`, `scripts/**`, `docs/demo.md`

## Mission
Make the project trivially runnable and demoable; document what the rubric checks.

## Deliverables
1. `scripts/dev.sh` — one command: create/activate `.venv`, install backend deps, run uvicorn (port 8000).
2. `scripts/dev-ui.sh` — `npm install` + vite dev (port 5173, proxy → 8000).
3. `scripts/verify.sh` — runs WS2 validator against all three reference CSVs from pre-ingested stores if present (pull/clone data/repos on demand); prints a pass/fail table.
4. `scripts/sample_data.sh` — clones cJSON/redis/git at the pinned SHAs into `data/repos/` (deep clones).
5. README rewrite: what it is, screenshots (from `docs/screens/`), quickstart (dev.sh), architecture diagram (mermaid: git → engine → SQLite → API → React), rubric mapping table, verification instructions, AI-usage notes.
6. `docs/demo.md` — 5-minute demo script mapped to the rubric tiers (multi-repo, ingestion both ways, filters, author merge incl. mailmap, browser, perf note on git.git).

## Acceptance
Fresh clone of the repo → `scripts/dev.sh` + `scripts/dev-ui.sh` → dashboard usable; `scripts/verify.sh` prints green for all three repos (post-S3).
