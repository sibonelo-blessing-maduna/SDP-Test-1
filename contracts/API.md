# Contract C — REST API (frozen)

**Owner:** integration (T0). **Consumers:** WS4 frontend, WS3 implementer.
Base path `/api`. JSON everywhere. Errors: `{"detail": "..."}` with proper HTTP status.

All metrics endpoints share the **filter params**:
- `from` (unix ts, inclusive), `to` (unix ts, exclusive) — committer-date window; default: full history
- `commits` — comma-separated shas; if present it **overrides** `from`/`to`
- `author` — restrict aggregates to one author (raw or merged name)

`{id}` is a slug (e.g. `cjson`). `path` is repo-relative; repository root is `/`.

## Repositories

| Method & path | Body | Returns |
| --- | --- | --- |
| `GET /api/repos` | — | `[{id, name, source, ref_sha, commit_count, status, progress}]` — `status ∈ scanning\|ready\|error` |
| `GET /api/repos/{id}` | — | same object as above + `{authors_count, files_count, dirs_count, error}` |
| `POST /api/repos/clone` | `{url, name?}` | `201 {id, status:"scanning"}` — deep clone + background scan |
| `POST /api/repos/upload` | multipart `file` = repo zip (with `.git`) | `201 {id, status:"scanning"}` |
| `GET /api/repos/{id}/status` | — | `{status, progress: 0..1, message}` — polled during scan |
| `DELETE /api/repos/{id}` | — | `204` |

## Commits (picker)

| Method & path | Returns |
| --- | --- |
| `GET /api/repos/{id}/commits?limit=100&offset=0&q=<search>&from=&to=` | `[{sha, ct, author, subject}]` (newest first; `q` matches author/subject) |

## Metrics

| Method & path | Returns |
| --- | --- |
| `GET /api/repos/{id}/metrics?path=/&from&to&commits&author` | object metrics + per-author breakdown (schema below) |
| `GET /api/repos/{id}/children?dir=/&from&to&commits&author&sort=churn&order=desc` | `[{name, path, type: file\|dir, added, removed, growth, churn, modifications, modification_frequency, churn_rate, ownership}]` — one row per immediate child, ALL-authors aggregate; `ownership` = share of selected author when `author` given |
| `GET /api/repos/{id}/series?path=/&from&to&commits&bucket=day\|week\|month` | `[{t, added, removed, growth, churn}]` — one point per bucket (bucket start ts) |
| `GET /api/repos/{id}/authors?from&to&commits` | `[{author, added, removed, growth, churn, modifications, commit_count, ownership}]` — repository-level per author |

`/metrics` response shape:
```json
{
  "object": {"type": "repository", "path": "/"},
  "commit_set": {"count": 955, "from": null, "to": null, "commits": null},
  "all": {"added": 46377, "removed": 11211, "growth": 35166, "churn": 57588,
           "modifications": 953, "modification_frequency": 0.9979, "churn_rate": 60.30157},
  "authors": [{"author": "Max Bruckner <max@maxbruckner.de>", "added": 39192, "...": "...", "ownership": 0.83684}]
}
```
(metric number formatting: full-precision JSON numbers; empty-string cells from the CSV schema become `null`.)

## Authors / merging

| Method & path | Body | Returns |
| --- | --- | --- |
| `POST /api/repos/{id}/authors/merge` | `{from: [<author>, ...], to: <author>}` | `200 {merges: {raw: merged}}` — read-time overlay, reversible |
| `POST /api/repos/{id}/authors/unmerge` | `{author: <raw>}` (or `{all: true}`) | `200 {merges: {...}}` |
| `POST /api/repos/{id}/mailmap/apply` | — | `200 {merges: {...}, applied: n}` — parses repo `.mailmap`, merges each raw author into its canonical form |
| `GET /api/repos/{id}/mailmap` | — | `{available: bool, entries: [{raw, canonical}]}` — dry-run preview |

## Mock fixtures

`fixtures/mock/*.json` mirror these shapes 1:1 (generated from `repo-references/cJSON_*.csv`).
WS4 must be able to develop the whole UI against the mock server before the real API exists.
