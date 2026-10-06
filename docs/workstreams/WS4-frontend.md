# WS4 — Frontend Dashboard (Vite + React)

**Branch:** `feat/ws4-ui` · **Owns:** `frontend/**`

## Mission
Build the graded surface: a multi-repo dashboard with excellent navigation, filters (repo, author,
file/dir, time window, manual commit list) and "inspired" visualisation of the metrics.

## Deliverables
1. Vite + React (JS ok) app; **no server dependency**: develop against `fixtures/mock/*.json`
   via a tiny local mock server (`frontend/mock/server.mjs`, serves fixtures; proxy switch to real API at S2).
2. Pages/components:
   - **Repos**: cards/table (status, commit count, sparkline of churn), add-repo modal (zip upload with drag&drop + clone URL), delete, scan progress
   - **Dashboard**: filter bar (time range presets + custom, author dropdown, commit picker modal with search/checkboxes/ranges), KPI stat cards, charts (recharts): churn-over-time area (stacked added/removed optional), top-churn files bar, directory treemap, authors bar + ownership donut
   - **Browser**: directory/file table (breadcrumb up/down, sortable metric columns incl. modifications/freq/rate/ownership, click dir → drill in; click file → per-author breakdown panel)
   - **Authors**: table (churn, commits, ownership, mods) + merge UI (multi-select → merge to target; unmerge chips) + "Apply .mailmap" with dry-run preview
   - **Commit picker modal**: virtualised list (repos can have 100k commits), search, select-all-in-window, manual selection summary chip
3. State: URL-driven filters (shareable links), loading skeletons, **empty/error states everywhere** (usability tier), dark theme, responsive >= 1280px.
4. `npm run build` works; `frontend/dist` consumable by WS3 static serving.

## Acceptance
- UI checklist walked against mock fixtures (screenshot each view into `docs/screens/`).
- At S2: same flows against the real API for cJSON; commit picker stays fluid on git.git-sized data (virtualisation).
