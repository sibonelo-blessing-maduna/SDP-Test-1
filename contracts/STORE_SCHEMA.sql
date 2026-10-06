-- Contract B — Store schema (frozen)
-- Owner: integration (T0). Consumers: WS1 engine (writers), WS3 API (readers).
-- One SQLite file per repo: data/db/<repo_id>.sqlite

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- Key/value metadata: name, source ("zip:<file>" | "url:<url>"), git_dir, ref_sha,
-- commit_count, scanned_at, engine_version, rename_mode.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- One row per commit in H̄ (non-merge commits reachable from ref).
CREATE TABLE IF NOT EXISTS commits (
    sha       TEXT PRIMARY KEY,   -- full 40-char
    ct        INTEGER NOT NULL,   -- committer timestamp (unix seconds)
    author    TEXT    NOT NULL,   -- raw "Name <email>"
    subject   TEXT
);
CREATE INDEX IF NOT EXISTS idx_commits_ct     ON commits(ct);
CREATE INDEX IF NOT EXISTS idx_commits_author ON commits(author);

-- Per-commit file changes. One row per (commit, path) with a real change (lambda > 0),
-- plus "touch markers" (added=removed=0) for pure renames / mode-only changes, so the
-- file universe can be reconstructed exactly. Binary files are not stored at all.
CREATE TABLE IF NOT EXISTS file_stats (
    sha     TEXT NOT NULL,
    path    TEXT NOT NULL,        -- new path for renames
    added   INTEGER NOT NULL,
    removed INTEGER NOT NULL,
    PRIMARY KEY (sha, path)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_file_stats_path ON file_stats(path);

-- Per-commit directory rollups, materialised for every ancestor directory
-- (including root '/') of every non-binary file entry in that commit.
-- needed for correct per-commit `modifications` counting on directories.
CREATE TABLE IF NOT EXISTS dir_stats (
    sha     TEXT NOT NULL,
    path    TEXT NOT NULL,        -- '/' for the repository root
    added   INTEGER NOT NULL,
    removed INTEGER NOT NULL,
    PRIMARY KEY (sha, path)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_dir_stats_path ON dir_stats(path);

-- Author merge mapping (feature/author-merge). raw -> merged. Absent = identity.
-- Metrics queries LEFT JOIN this via commits.author; merges are a read-time overlay,
-- commit rows are never rewritten (so merges are reversible).
CREATE TABLE IF NOT EXISTS author_merges (
    raw       TEXT PRIMARY KEY,
    merged    TEXT NOT NULL
);

-- Progress/reporting for background scans (written by engine, read by API).
CREATE TABLE IF NOT EXISTS scan_log (
    ts      INTEGER,
    level   TEXT,                 -- info | warn | error
    message TEXT
);

-- Query semantics (WS3 must implement exactly):
--   object metrics for commit set H (H = all commits matching ct/commit filters):
--     file:  SUM/COUNT to file_stats WHERE path = ?
--     dir:   same over dir_stats  (root object -> path = '/')
--     |H|   = COUNT(*) FROM commits (filtered)   -- includes commits with no changes
--     modifications = COUNT(*) of stats rows with added+removed > 0
--     author rows: GROUP BY commits.author (LEFT JOIN author_merges for merged name)
--     modification_frequency = modifications/|H|; churn_rate = churn/|H|
--     ownership = author churn / object churn (0 when object churn = 0)
