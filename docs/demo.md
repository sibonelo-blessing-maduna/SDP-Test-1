# Demo guide — RAT (COMS3011A)

How to run and present the Repo Analysis Tool, and where each rubric tier is
demonstrated.

## 0. Prepare (once)

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
bash scripts/fetch_repos.sh     # clone cJSON / redis / git at the pinned SHAs
bash scripts/sample_data.sh     # engine scan -> data/db/*.sqlite + catalog
bash scripts/serve.sh           # http://localhost:8000  (API + UI on one port)
```

The three reference repositories are pre-loaded and `ready`. `scripts/serve.sh`
serves the REST API **and** the built React app from FastAPI on a single port;
`scripts/dev.sh` is the hot-reload variant for development.

## 1. Demo script (≈10 minutes)

1. **Repositories** (`#/`) — three cards: cJSON (955 commits), redis (11 874),
   git (61 101), each with a weekly-churn sparkline. Show **Add repository**:
   *Clone URL* tab and *Zip upload* tab (drag & drop). Nothing else to set up.
2. **Dashboard — cJSON** — KPI cards mirror the reference CSV exactly
   (added 46 377, removed 11 211, growth 35 166, churn 57 588, modifications
   953). Charts: churn-over-time (diverging added/removed + growth line), top
   files by churn, ownership donut (Max Bruckner ≈ 83.7 %), root treemap,
   top authors.
3. **Filters** — press the "30 days" preset: KPIs and charts recompute and the
   URL updates (shareable link, e.g.
   `#/repos/cjson?from=…&author=…`). Pick an author — the chip appears and the
   dashboard reflects only their churn. Open **Pick commits**: search
   (`heap`), shift-click a range, *Apply selection* → chip shows *n commits
   (manual commit list overrides the time window)*.
4. **Browser** — root children in a sortable table (type badge, added, removed,
   growth, churn, modifications, freq, churn rate, ownership). Drill into
   `tests/`; breadcrumb + *Up* navigate. Click a file (`cJSON.c`) for the
   per-author breakdown panel with the ALL row on top.
5. **Authors** — sort by churn/ownership. Tick two authors, *Merge into* the
   target, *Merge* → chips (raw → canonical) appear, the table regroups with
   summed metrics; unmerge a single chip or all. Show **.mailmap** (on the git
   repo: preview entries, then *Apply .mailmap*).
6. **Scale** — switch to **git** in the repo switcher: 61 101 commits. The
   commit picker stays fluid (virtualised windowed list, 200 commits per page,
   scroll-to-load) and the dashboard still matches the git reference totals
   (added 9 505 538 … growth …). Try the 1-year preset on redis too.
7. **Ingestion** — *Add repository* → **Zip upload** → drag
   `fixtures/tiny_repo.zip` (built by `tests/fixture_repo.py`). The card shows a
   live scan progress bar (polling `/status`), then flips to *ready*. Open it:
   rename handling (`hello.txt` → `src/hello.py` attributed to the new path),
   unicode author (Ólafur) and path (`docs/café.txt`), the binary `logo.bin`
   skipped, deleted `docs/readme.md` history still visible in the Browser.
   Finally *Delete* the repo (204 + card disappears).
8. **Proof** — run `bash scripts/verify.sh` in a terminal: byte-exact diffs
   against all three references ("EXACT MATCH", 0 missing / 0 extra / 0
   mismatches per column) plus the 35-test suite. Optionally open
   `repo-references/cJSON_*.csv` next to the engine export
   (`python -m rat_engine export --db data/db/cjson.sqlite --out /tmp/x.csv`)
   in a diff tool.

## 2. Rubric mapping

| Tier | Where it shows |
| --- | --- |
| Functionality | Exact metrics for all 3 reference repos (validator + `scripts/verify.sh`); all metric columns and all object types (file/directory/repository, ALL + per author); time-window, author and manual commit-list filters; multi-repo (cards, switcher); ingestion via clone URL *and* zip upload with background scan + progress; author merge/unmerge + `.mailmap`. |
| Usability | URL-driven filters (every view is a shareable link); loading skeletons per widget; empty states (empty dir, no authors, empty search, no repos) and error states with retry; dark theme; responsive plan ≥1280 px; Esc/overlay closes modals; delete confirmations are two-step. |
| Beyond spec | Virtualised commit picker that stays fluid on git.git (61 k commits); strict validator with full-column checking, tolerance flag and ignore-paths; mutation-detection proof suite; deterministic fixture repo + byte-stable mock fixtures; benchmark tool; frozen contracts + workstream branches in git history. |

## 3. Engineering notes worth mentioning

- **Contract-first**: three frozen contracts (engine CSV semantics, SQLite
  schema, REST API) were written before the workstreams and let the frontend,
  backend and engine proceed independently (mock server → proxy switch).
- **Byte-exactness discipline**: the validator compares every column of every
  row against the reference; the engine recipe is pinned by the reference CSVs
  themselves (mailmap-canonical authors, 0/0 rename touch markers on both sides,
  binary skip, reciprocal-multiplied rates).
- **Decimal handling**: rates use reciprocal multiplication (×1/|H|) matching
  the oracle's rounding; ownership is a direct division. `--tol` exists for
  experiments but the default gate is exact.

## 4. Troubleshooting

- Port busy: `PORT=9000 bash scripts/serve.sh`.
- No data: make sure `scripts/fetch_repos.sh` + `scripts/sample_data.sh` ran, or
  upload a repo through the UI (zip must contain `.git`).
- Frontend changes not visible: `cd frontend && npm run build` (or use
  `scripts/dev.sh`).
