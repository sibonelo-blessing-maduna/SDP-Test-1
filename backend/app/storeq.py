"""Real-store queries: Contract B semantics in, Contract C shapes out."""
from __future__ import annotations

import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rat_engine import store as engine_store

SQL_TABLE = {"file": "file_stats", "directory": "dir_stats", "repository": "dir_stats"}


def connect_ro(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def connect_rw(db_path: str):
    conn = engine_store.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _likes(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filter_sql(from_ts, to_ts, commits):
    where, params = [], []
    if commits:
        marks = ",".join("?" for _ in commits)
        where.append(f"c.sha IN ({marks})")
        params.extend(commits)
    else:
        if from_ts is not None:
            where.append("c.ct >= ?")
            params.append(int(from_ts))
        if to_ts is not None:
            where.append("c.ct < ?")
            params.append(int(to_ts))
    return where, params


def _cond(where):
    return (" AND " + " AND ".join(where)) if where else ""


def _h(conn, from_ts, to_ts, commits) -> int:
    where, params = _filter_sql(from_ts, to_ts, commits)
    sql = f"SELECT COUNT(*) n FROM commits c" + ((" WHERE " + " AND ".join(where)) if where else "")
    return conn.execute(sql, params).fetchone()["n"]


def object_type_of(conn, path: str) -> str | None:
    if path in ("", "/"):
        return "repository"
    if conn.execute("SELECT 1 FROM file_stats WHERE path=? LIMIT 1", (path,)).fetchone():
        return "file"
    if conn.execute("SELECT 1 FROM dir_stats WHERE path=? LIMIT 1", (path,)).fetchone():
        return "directory"
    return None


def object_metrics(conn, path: str = "/", from_ts=None, to_ts=None,
                   commits=None, author=None) -> dict | None:
    path = path or "/"
    otype = object_type_of(conn, path)
    if otype is None:
        return None
    table = SQL_TABLE[otype]
    where, params = _filter_sql(from_ts, to_ts, commits)
    cond = _cond(where)
    h = _h(conn, from_ts, to_ts, commits)

    agg = conn.execute(
        f"SELECT COALESCE(SUM(fs.added),0) a, COALESCE(SUM(fs.removed),0) r,"
        f" COALESCE(SUM(CASE WHEN fs.added+fs.removed>0 THEN 1 ELSE 0 END),0) m"
        f" FROM {table} fs JOIN commits c ON c.sha=fs.sha WHERE fs.path=?{cond}",
        [path, *params]).fetchone()
    a, r, mobj = agg["a"], agg["r"], agg["m"]
    churn = a + r

    authors = []
    for row in conn.execute(
            f"SELECT COALESCE(m2.merged, c.author) author, SUM(fs.added) a, SUM(fs.removed) r,"
            f" SUM(CASE WHEN fs.added+fs.removed>0 THEN 1 ELSE 0 END) n"
            f" FROM {table} fs JOIN commits c ON c.sha=fs.sha"
            f" LEFT JOIN author_merges m2 ON m2.raw=c.author"
            f" WHERE fs.path=?{cond} GROUP BY 1 HAVING SUM(fs.added)+SUM(fs.removed)>0",
            [path, *params]).fetchall():
        ac = row["a"] + row["r"]
        authors.append({
            "author": row["author"], "added": row["a"], "removed": row["r"],
            "growth": row["a"] - row["r"], "churn": ac, "modifications": row["n"],
            "modification_frequency": None, "churn_rate": None,
            "ownership": (ac / churn) if churn else 0.0,
        })
    authors.sort(key=lambda x: (-x["churn"], x["author"]))
    if author:
        authors = [x for x in authors if x["author"] == author]

    return {
        "object": {"type": otype, "path": path},
        "commit_set": {"count": h, "from": from_ts, "to": to_ts, "commits": commits or None},
        "all": {
            "added": a, "removed": r, "growth": a - r, "churn": churn,
            "modifications": mobj,
            "modification_frequency": (mobj * (1.0 / h)) if h else 0.0,
            "churn_rate": (churn * (1.0 / h)) if h else 0.0,
            "ownership": None,
        },
        "authors": authors,
    }


def children(conn, dir_path: str = "/", from_ts=None, to_ts=None, commits=None,
             author=None, sort: str = "churn", order: str = "desc") -> list:
    dir_path = dir_path or "/"
    prefix = "" if dir_path == "/" else dir_path.rstrip("/") + "/"
    where, params = _filter_sql(from_ts, to_ts, commits)
    cond = _cond(where)
    esc = _likes(prefix) + "%"
    h = _h(conn, from_ts, to_ts, commits)

    out = []
    for table, otype in (("dir_stats", "dir"), ("file_stats", "file")):
        for row in conn.execute(
                f"SELECT fs.path, SUM(fs.added) a, SUM(fs.removed) r,"
                f" SUM(CASE WHEN fs.added+fs.removed>0 THEN 1 ELSE 0 END) n"
                f" FROM {table} fs JOIN commits c ON c.sha=fs.sha"
                f" WHERE fs.path LIKE ? ESCAPE '\\'{cond} GROUP BY fs.path",
                [esc, *params]).fetchall():
            rest = row["path"][len(prefix):]
            if not rest or "/" in rest:
                continue
            churn = row["a"] + row["r"]
            out.append({
                "name": rest, "path": row["path"], "type": otype,
                "added": row["a"], "removed": row["r"],
                "growth": row["a"] - row["r"], "churn": churn,
                "modifications": row["n"],
                "modification_frequency": (row["n"] * (1.0 / h)) if h else 0.0,
                "churn_rate": (churn * (1.0 / h)) if h else 0.0,
                "ownership": None,
            })

    if author:
        owner = {}
        for table in ("dir_stats", "file_stats"):
            for row in conn.execute(
                    f"SELECT fs.path, SUM(fs.added)+SUM(fs.removed) ch"
                    f" FROM {table} fs JOIN commits c ON c.sha=fs.sha"
                    f" LEFT JOIN author_merges m2 ON m2.raw=c.author"
                    f" WHERE fs.path LIKE ? ESCAPE '\\' AND COALESCE(m2.merged,c.author)=?{cond}"
                    f" GROUP BY fs.path",
                    [esc, author, *params]).fetchall():
                owner[row["path"]] = row["ch"]
        for item in out:
            ac = owner.get(item["path"], 0)
            item["ownership"] = (ac / item["churn"]) if item["churn"] else 0.0

    if sort == "name":
        out.sort(key=lambda x: (x["name"].lower(), x["path"]), reverse=(order == "desc"))
    else:
        key = sort if sort in ("churn", "growth", "added", "removed", "modifications") else "churn"
        out.sort(key=lambda x: (x[key], x["name"]), reverse=(order != "asc"))
    return out


def _bucket_start(ts: int, bucket: str) -> int:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if bucket == "month":
        dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif bucket == "week":
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        dt = dt - timedelta(days=dt.weekday())
    else:  # day
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(dt.timestamp())


def series(conn, path: str = "/", bucket: str = "week", from_ts=None, to_ts=None,
           commits=None) -> list | None:
    path = path or "/"
    otype = object_type_of(conn, path)
    if otype is None:
        return None
    table = SQL_TABLE[otype]
    where, params = _filter_sql(from_ts, to_ts, commits)
    cond = _cond(where)
    buckets: dict[int, dict] = {}
    for row in conn.execute(
            f"SELECT c.ct ct, SUM(fs.added) a, SUM(fs.removed) r"
            f" FROM {table} fs JOIN commits c ON c.sha=fs.sha"
            f" WHERE fs.path=?{cond} GROUP BY c.sha ORDER BY c.ct",
            [path, *params]).fetchall():
        t = _bucket_start(row["ct"], bucket)
        b = buckets.setdefault(t, {"t": t, "added": 0, "removed": 0})
        b["added"] += row["a"]
        b["removed"] += row["r"]
    out = sorted(buckets.values(), key=lambda b: b["t"])
    for b in out:
        b["growth"] = b["added"] - b["removed"]
        b["churn"] = b["added"] + b["removed"]
    return out


def repo_authors(conn, from_ts=None, to_ts=None, commits=None) -> list:
    where, params = _filter_sql(from_ts, to_ts, commits)
    cond = _cond(where)
    stats: dict[str, dict] = {}
    for row in conn.execute(
            f"SELECT COALESCE(m2.merged, c.author) a, SUM(fs.added) ad, SUM(fs.removed) rm,"
            f" SUM(CASE WHEN fs.added+fs.removed>0 THEN 1 ELSE 0 END) n"
            f" FROM dir_stats fs JOIN commits c ON c.sha=fs.sha"
            f" LEFT JOIN author_merges m2 ON m2.raw=c.author"
            f" WHERE fs.path='/'{cond} GROUP BY 1", params).fetchall():
        stats[row["a"]] = {"added": row["ad"], "removed": row["rm"], "modifications": row["n"]}
    counts: dict[str, int] = {}
    for row in conn.execute(
            f"SELECT COALESCE(m2.merged, c.author) a, COUNT(*) n FROM commits c"
            f" LEFT JOIN author_merges m2 ON m2.raw=c.author"
            + (f" WHERE {(' AND '.join(where))}" if where else "") + " GROUP BY 1",
            params).fetchall():
        counts[row["a"]] = row["n"]

    total_churn = sum(s["added"] + s["removed"] for s in stats.values())
    out = []
    for name in set(stats) | set(counts):
        s = stats.get(name, {"added": 0, "removed": 0, "modifications": 0})
        churn = s["added"] + s["removed"]
        out.append({
            "author": name, "added": s["added"], "removed": s["removed"],
            "growth": s["added"] - s["removed"], "churn": churn,
            "modifications": s["modifications"], "commit_count": counts.get(name, 0),
            "ownership": (churn / total_churn) if total_churn else 0.0,
        })
    out.sort(key=lambda x: (-x["churn"], x["author"]))
    return out


def commits_list(conn, limit: int = 100, offset: int = 0, q: str | None = None,
                 from_ts=None, to_ts=None) -> list:
    where, params = _filter_sql(from_ts, to_ts, None)
    if q:
        qq = f"%{_likes(q)}%"
        where.append("(c.author LIKE ? ESCAPE '\\' OR c.subject LIKE ? ESCAPE '\\')")
        params.extend([qq, qq])
    cond = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT c.sha, c.ct, c.author, c.subject FROM commits c{cond}"
        f" ORDER BY c.ct DESC, c.sha LIMIT ? OFFSET ?",
        [*params, int(limit), int(offset)]).fetchall()
    return [{"sha": r["sha"], "ct": r["ct"], "author": r["author"], "subject": r["subject"]}
            for r in rows]


def repo_counts(conn) -> dict:
    return {
        "authors_count": conn.execute("SELECT COUNT(DISTINCT author) n FROM commits").fetchone()["n"],
        "files_count": conn.execute("SELECT COUNT(DISTINCT path) n FROM file_stats").fetchone()["n"],
        "dirs_count": conn.execute("SELECT COUNT(DISTINCT path) n FROM dir_stats").fetchone()["n"],
    }


def list_merges(conn) -> dict:
    return dict(conn.execute("SELECT raw, merged FROM author_merges").fetchall())


def set_merge(conn, raws: list, target: str) -> dict:
    target = (target or "").strip()
    if not target:
        raise ValueError("target author is required")
    raws = [r for r in raws if r and r != target]
    conn.executemany("INSERT OR REPLACE INTO author_merges(raw, merged) VALUES (?,?)",
                     [(r, target) for r in raws])
    conn.execute("DELETE FROM author_merges WHERE raw = merged")
    conn.commit()
    return list_merges(conn)


def unmerge(conn, raw: str | None = None, all_: bool = False) -> dict:
    if all_:
        conn.execute("DELETE FROM author_merges")
    elif raw:
        conn.execute("DELETE FROM author_merges WHERE raw=? OR merged=?", (raw, raw))
    conn.commit()
    return list_merges(conn)


def mailmap_preview(conn, git_dir: str) -> dict:
    raws = [r["author"] for r in conn.execute("SELECT DISTINCT author FROM commits").fetchall()]
    available = (Path(git_dir) / ".mailmap").exists()
    if not raws:
        return {"available": available, "entries": []}
    proc = subprocess.run(["git", "-C", str(git_dir), "check-mailmap", "--stdin"],
                          input="\n".join(raws), capture_output=True, text=True)
    canon = proc.stdout.splitlines()
    entries = []
    for raw, c in zip(raws, canon):
        c = c.strip()
        if c and c != raw:
            entries.append({"raw": raw, "canonical": c})
    return {"available": available, "entries": entries}


def apply_mailmap(conn, git_dir: str) -> dict:
    preview = mailmap_preview(conn, git_dir)
    by_target: dict[str, list] = {}
    for entry in preview["entries"]:
        by_target.setdefault(entry["canonical"], []).append(entry["raw"])
    for target, raws in by_target.items():
        set_merge(conn, raws, target)
    return {"applied": sum(len(v) for v in by_target.values()),
            "available": preview["available"],
            "entries": preview["entries"]}
