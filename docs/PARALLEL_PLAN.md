# Parallel execution plan — RAT (COMS3011A test)

## Principle

All semantic risk is concentrated in **one seam**: git plumbing → per-object metrics (WS1).
Everything downstream consumes aggregates and is decoupled by **frozen contracts**:

| Contract | File | Freezes |
| --- | --- | --- |
| A — engine output | `contracts/ENGINE_OUTPUT.md` | reference CSV schema + matching semantics + engine CLI |
| B — store schema | `contracts/STORE_SCHEMA.sql` | SQLite tables + query semantics |
| C — REST API | `contracts/API.md` | endpoints, params, response shapes |

Contracts are owned by integration; change requests must propose a diff to the contract file.

## Workstreams

| WS | Scope | Branch | Owned paths | Inputs | Acceptance |
| --- | --- | --- | --- | --- | --- |
| WS1 | Engine: git scan → SQLite; metrics; perf | `feat/ws1-engine` | `backend/rat_engine/**` | Contract A+B, `repo-references/` | `rat_engine export` ≡ reference CSV for cJSON → redis → git (byte-exact numeric match via WS2 tool) |
| WS2 | Validator/QA: CSV differ, fixtures, perf harness | `feat/ws2-validator` | `tools/**`, `fixtures/**`, `tests/**` | Contract A | `tools/rat_validate.py` detects every injected mutation; fixture builder regenerates `fixtures/mock/` |
| WS3 | Backend API: FastAPI, ingestion (zip/clone), filters, author merge | `feat/ws3-api` | `backend/app/**`, `backend/requirements.txt` | Contract B+C + `fixtures/mock/` | contract tests pass against fixture store; flips to real store by env var |
| WS4 | Frontend: Vite/React dashboard | `feat/ws4-ui` | `frontend/**` | Contract C + `fixtures/mock/` | UI checklist vs mock; then proxy → real API |
| WS5 | Infra/Docs/Demo | `chore/ws5-infra-docs` | `README.md`, `scripts/**`, `docs/demo.md` | all contracts | fresh clone → `scripts/dev.sh` runs both servers; demo script walks the rubric |

## Sync points

- **S1** — WS1 emits a cJSON CSV that WS2's validator reports as *exact match* → WS3 switches from fixture store to the real store; WS4 keeps using mock until S2.
- **S2** — real API up locally → WS4 flips proxy to live API; E2E pass on cJSON.
- **S3** — full validation on all three reference repos (+ git.git ingest perf) → docs/demo polish → final merges to `main`.

## Rules of engagement

1. One branch per WS; **never** edit another WS's owned paths. Cross-cutting needs → contract change request to integration.
2. `main` receives merges only at sync points (or when integration says so), via the integration owner.
3. Every WS keeps its own acceptance test runnable **without** other WSs (fixtures/mocks are provided for exactly this).
4. Commits: conventional style (`feat(engine): ...`), small and frequent; push to your branch early.
5. Python env: repo-root `.venv` (`python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`); Node 18 + npm for WS4.
