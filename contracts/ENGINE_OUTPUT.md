# Contract A — Engine Output (frozen)

**Owner:** integration (T0). **Consumers:** WS2 validator, WS3 API (export endpoints), WS5 docs.
Change requests go through the integration owner only.

## 1. Metric CSV schema (must be byte-compatible with `repo-references/*.csv`)

Header (exactly):

```
repo,ref_sha,commit_set,commit_count,object_type,path,author,added,removed,growth,churn,modifications,modification_frequency,churn_rate,ownership
```

| Column | Type | Semantics |
| --- | --- | --- |
| `repo` | str | repository name (`cJSON`, `git`, `redis`, or user-chosen) |
| `ref_sha` | str | full 40-char sha of the reference commit |
| `commit_set` | str | `all` for full history; `time:<from>-<to>` / `manual` reserved for filtered exports |
| `commit_count` | int | \|H\| — number of commits *selected* (not only changed), non-merge reachable from `ref_sha` |
| `object_type` | enum | `repository` \| `directory` \| `file` |
| `path` | str | `/` for repository; repo-relative path otherwise (e.g. `src/a.c`, `.github`) |
| `author` | str | `ALL` for the aggregate row; else canonical `Name <email>` from `%aN <%aE>` — **mailmap-aware** (repos without `.mailmap` are unaffected) |
| `added` | int | Σ l⁺ over H |
| `removed` | int | Σ l⁻ over H |
| `growth` | int | Σ δ = added − removed |
| `churn` | int | Σ λ = added + removed |
| `modifications` | int | # commits h∈H with λ_{h,o} > 0 |
| `modification_frequency` | float / empty | n/|H| if |H|≠0 else 0 — **ALL rows only**, empty on author rows |
| `churn_rate` | float / empty | λ/|H| if |H|≠0 else 0 — **ALL rows only**, empty on author rows |
| `ownership` | float / empty | λ_{H,o,a}/λ_{H,o} if λ≠0 else 0 — **author rows only**, empty on ALL row |

Row set per object `o ∈ H[F] ∪ H[D]`:
one `ALL` row, then one row per author who touched `o` (author rows sorted: by added desc as in reference — irrelevant, validator matches on keys).

Floats are written with Python `repr()` (shortest round-trip), exactly like the reference files.
Rates are computed as `x * (1/|H|)` (multiply by reciprocal) — direct division differs by up to 1 ulp and breaks byte compatibility. `ownership` is a direct division `churn_a / churn_ALL`.
Rows ordered as: repository rows, then directories (path asc), then files (path asc) — order is not part of the contract; consumers must match by `(object_type, path, author)`.

## 2. Matching semantics (empirically pinned against all three reference CSVs)

1. Universe H̄: `git rev-list --no-merges <ref>` — `commit_count` = its size.
2. Per-commit entries: `git log --no-merges --numstat -z -M50% <ref>` — **never path-filtered** (path filters invoke history simplification and drop commits).
3. Attribution: every numstat entry is attributed **verbatim to its path** (`$path` field). Nonzero rename pairs detected at 50% similarity are attributed to the **new path** only; `0/0` entries (pure renames) are kept as touch markers on **both sides** — old and new paths each get an all-zero `ALL` row and **no author rows**. Do not create synthetic `old => new` paths.
4. Binary entries (`-\t-\t...`) are skipped entirely.
5. Author identity: `%aN <%aE>` — mailmap-canonical (git repo collapses 2807 raw identities to the reference's 2498); committer date `%ct` for all time filters. Non-UTF-8 name bytes are decoded with `errors="replace"`.
6. Directory rows = rollup over every ancestor directory (including `/`) of each changed file, **per commit** (needed for correct `modifications` counting).
7. `modifications`: count commits where λ>0 — a pure mode change / pure `0/0` rename is *not* a modification (it produces only the all-zero ALL row).
8. Author rows: per `(path, author)` sums over that author's commits; emitted **only when the author's total churn for the object is > 0**; `ownership = churn_a / churn_ALL`.
9. Empty-string cells: `modification_frequency` + `churn_rate` on author rows; `ownership` on ALL rows.

## 3. CLI (reference implementation: `backend/rat_engine`)

```
python -m rat_engine scan   --repo <path> --name <name> --db <store.sqlite> [--ref <sha>]
python -m rat_engine export --db <store.sqlite> [--ref <sha>] [--from <ts>] [--to <ts>]
                            [--commits <sha,sha,...>] [--author <name>] [--object <path>]
```

- `scan` resolves `--ref` (default `HEAD`), walks history, writes the store. Idempotent: rescan of same ref replaces rows.
- `export` writes the CSV (schema above) to stdout.
- Exit code 0 on success; validation is WS2's job (`tools/rat_validate.py`).
