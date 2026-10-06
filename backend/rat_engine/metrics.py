"""Contract A metric rows from the Contract B store (query semantics per STORE_SCHEMA.sql).

Semantics pinned against repo-references/*.csv (see contracts/ENGINE_OUTPUT.md):
  * ALL row  : modification_frequency + churn_rate filled, ownership empty
  * author row: ownership filled, modification_frequency + churn_rate empty
  * ownership = churn_author / churn_ALL (0 when object churn is 0)
  * author rows only when the author's total churn for the object is > 0
    (a pure 0/0 touch marker creates the object row but no author row)
  * rates use multiplication by (1/|H|) — direct division is 1 ulp off vs the reference
  * floats written with Python repr(); |H| always includes unchanged commits
"""
from __future__ import annotations

HEADER = ["repo", "ref_sha", "commit_set", "commit_count", "object_type", "path",
          "author", "added", "removed", "growth", "churn", "modifications",
          "modification_frequency", "churn_rate", "ownership"]

TABLE_FOR = {"file": "file_stats", "directory": "dir_stats"}


def _filter_sql(alias: str, from_ts, to_ts, commits):
    where, params = [], []
    if commits:
        marks = ",".join("?" for _ in commits)
        where.append(f"{alias}.sha IN ({marks})")
        params.extend(commits)
    else:
        if from_ts is not None:
            where.append(f"{alias}.ct >= ?")
            params.append(int(from_ts))
        if to_ts is not None:
            where.append(f"{alias}.ct < ?")
            params.append(int(to_ts))
    return (" WHERE " + " AND ".join(where) if where else ""), params


def _f(v):
    return "" if v is None else repr(float(v))


def export_rows(conn, *, from_ts=None, to_ts=None, commits=None,
                author=None, object_path=None, repo_label=None, ref_sha=None) -> list:
    if repo_label is None or ref_sha is None:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        repo_label = repo_label if repo_label is not None else meta.get("name", "")
        ref_sha = ref_sha if ref_sha is not None else meta.get("ref_sha", "")
    commits = [c for c in (commits or []) if c]

    wc, pc = _filter_sql("c", from_ts, to_ts, commits)
    h = conn.execute(f"SELECT COUNT(*) FROM commits c{wc}", pc).fetchone()[0]

    if commits:
        set_label = "manual"
    elif from_ts is not None or to_ts is not None:
        set_label = f"time:{from_ts if from_ts is not None else ''}-{to_ts if to_ts is not None else ''}"
    else:
        set_label = "all"

    merge_join = "LEFT JOIN author_merges m ON m.raw = c.author"
    author_expr = "COALESCE(m.merged, c.author)"

    def all_rows(table):
        sql = (f"SELECT fs.path, SUM(fs.added), SUM(fs.removed), "
               f"SUM(CASE WHEN fs.added + fs.removed > 0 THEN 1 ELSE 0 END) "
               f"FROM {table} fs JOIN commits c ON c.sha = fs.sha{wc} GROUP BY fs.path")
        return {p: (a, r, n) for p, a, r, n in conn.execute(sql, pc).fetchall()}

    def author_rows(table):
        sql = (f"SELECT fs.path, {author_expr} AS author, SUM(fs.added), SUM(fs.removed), "
               f"SUM(CASE WHEN fs.added + fs.removed > 0 THEN 1 ELSE 0 END) "
               f"FROM {table} fs JOIN commits c ON c.sha = fs.sha {merge_join}{wc} "
               f"GROUP BY fs.path, {author_expr} "
               f"HAVING SUM(fs.added) + SUM(fs.removed) > 0")
        out = {}
        for p, a, added, removed, n in conn.execute(sql, pc).fetchall():
            out.setdefault(p, []).append((a, added, removed, n))
        return out

    files_all, dirs_all = all_rows("file_stats"), all_rows("dir_stats")
    files_auth, dirs_auth = author_rows("file_stats"), author_rows("dir_stats")

    def block(obj_type, path, all_stats, auth_stats):
        a, r, mods = all_stats
        growth, churn = a - r, a + r
        rows = [[repo_label, ref_sha, set_label, h, obj_type, path, "ALL",
                 a, r, growth, churn, mods,
                 _f(mods * (1.0 / h)) if h else _f(0.0),
                 _f(churn * (1.0 / h)) if h else _f(0.0), ""]]
        authors = sorted(auth_stats.get(path, []), key=lambda t: (-t[1], t[0]))
        for name, aa, ar, an in authors:
            if author and name != author:
                continue
            ac = aa + ar
            rows.append([repo_label, ref_sha, set_label, h, obj_type, path, name,
                         aa, ar, aa - ar, ac, an, "", "",
                         _f(ac / churn) if churn else _f(0.0)])
        return rows

    out = []
    if object_path in (None, "/"):
        if "/" in dirs_all:
            out.extend(block("repository", "/", dirs_all["/"], dirs_auth))
    if object_path is None:
        for path in sorted(p for p in dirs_all if p != "/"):
            out.extend(block("directory", path, dirs_all[path], dirs_auth))
        for path in sorted(files_all):
            out.extend(block("file", path, files_all[path], files_auth))
    elif object_path != "/":
        if object_path in files_all:
            out.extend(block("file", object_path, files_all[object_path], files_auth))
        elif object_path in dirs_all:
            out.extend(block("directory", object_path, dirs_all[object_path], dirs_auth))
        else:
            raise SystemExit(f"object {object_path!r} not found in store")
    return out
