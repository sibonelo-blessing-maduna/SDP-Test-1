# RAT frontend (WS4)

Vite + React dashboard for the Repo Analysis Tool. Talks to the frozen
Contract C REST API (`contracts/API.md`) through `/api`.

## Develop

```bash
npm install

# against the mock server (fixtures/mock/*.json — no backend needed)
npm run mock        # terminal 1: mock API on :5175
npm run dev         # terminal 2: app on :5173 (proxy -> :5175 by default)

# against the real API
npm run dev         # with VITE_PROXY_TARGET=http://127.0.0.1:8000
```

## Build & serve

```bash
npm run build       # -> frontend/dist (served by FastAPI, see scripts/serve.sh)
```

`frontend/dist` is picked up automatically by the backend: run
`bash scripts/serve.sh` for the full app on http://localhost:8000.

## Layout

| Path | Purpose |
| --- | --- |
| `src/App.jsx` | hash router (`#/repos/<id>/<page>?filters…`), top nav, repo switcher |
| `src/hooks.js` | router, `useApi`, formatters, filter (URL query) helpers |
| `src/api.js` | Contract C client (`/api/...`) |
| `src/components/` | FilterBar, CommitPicker (virtualised), Table, Charts (recharts), StatCards, Modal, states |
| `src/pages/` | Repos (cards + add-repo modal) · Dashboard (KPIs + charts) · Browser (drill-down + per-author panel) · Authors (merge + .mailmap) |
| `mock/server.mjs` | zero-dependency fixtures server (merge state in memory, simulated scans) |

Filters (time window, author, manual commit list, browser path) live entirely in
the URL query string — every view is a shareable link. The mock server documents
its approximations in `mock/server.mjs`; the real backend is exact.
