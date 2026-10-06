#!/usr/bin/env python3
"""Generate fixtures/mock/*.json (Contract C shapes) from repo-references CSVs (+ local clones).

Usage:  python tools/make_fixtures.py
Sources:
  repo-references/*.csv                 -> metrics, authors, children (always available)
  data/repos/<name>/ (git clone)        -> commits list, weekly churn series, author commit counts
                                           (when absent: deterministic synthetic placeholders,
                                           flagged in fixtures/mock/README.md)
# fixture-data: deterministic; regenerating with the same inputs yields identical output
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "fixtures" / "mock"

REPOS = [
    {"id": "cjson", "name": "cJSON", "clone_dir": "cJSON",
     "csv": "cJSON_6d9f2443ab07.csv", "source": "https://github.com/DaveGamble/cJSON.git"},
    {"id": "redis", "name": "redis", "clone_dir": "redis",
     "csv": "redis_b540ca49cba8.csv", "source": "https://github.com/redis/redis.git"},
    {"id": "git", "name": "git", "clone_dir": "git",
     "csv": "git_5a7d1e8045ce.csv", "source": "https://github.com/git/git.git"},
]

METRIC_INT = ("added", "removed", "growth", "churn", "modifications")
METRIC_FLOAT = ("modification_frequency", "churn_rate", "ownership")


def cell_num(row: dict, field: str):
    v = (row.get(field) or "").strip()
    if v == "":
        return None
    if field in METRIC_INT:
        return int(v)
    return float(v)


def load_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def metric_row(row: dict) -> dict:
    return {f: cell_num(row, f) for f in METRIC_INT + METRIC_FLOAT}


def children_of(rows: list, prefix: str) -> list:
    """Immediate children table for a directory prefix ('' = root), ALL rows only, churn desc."""
    out = []
    for r in rows:
        if r["author"] != "ALL" or r["object_type"] == "repository":
            continue
        p = r["path"]
        if not p.startswith(prefix):
            continue
        rest = p[len(prefix):]
        if rest == "" or ("/" in rest):
            continue
        item = {"name": rest, "path": p, "type": r["object_type"]}
        item.update(metric_row(r))
        out.append(item)
    out.sort(key=lambda x: (-(x["churn"] or 0), x["path"]))
    return out


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True
    ).stdout


def commits_fixture(clone: Path, limit: int = 200) -> list:
    raw = git(clone, "log", "--no-merges", f"-{limit}", "--format=%H%x1f%ct%x1f%aN <%aE>%x1f%s")
    out = []
    for line in raw.splitlines():
        sha, ct, author, subject = line.split("\x1f", 3)
        out.append({"sha": sha, "ct": int(ct), "author": author, "subject": subject})
    return out


def weekly_series(clone: Path) -> list:
    """Churn series bucketed by ISO week from a plain numstat pass (mock data only, not grading output)."""
    raw = git(clone, "log", "--no-merges", "--numstat", "-M50%", "--format=C%ct")
    buckets: dict[int, dict] = {}
    ct = None
    for line in raw.splitlines():
        if line.startswith("C") and line[1:].isdigit():
            ct = int(line[1:])
            continue
        parts = line.split("\t")
        if len(parts) < 3 or parts[0] == "-" or ct is None:
            continue
        iso = datetime.fromtimestamp(ct, tz=timezone.utc).isocalendar()
        week_start = datetime.fromisocalendar(iso.year, iso.week, 1).replace(tzinfo=timezone.utc)
        t = int(week_start.timestamp())
        b = buckets.setdefault(t, {"t": t, "added": 0, "removed": 0})
        b["added"] += int(parts[0])
        b["removed"] += int(parts[1])
    series = sorted(buckets.values(), key=lambda b: b["t"])
    for b in series:
        b["growth"] = b["added"] - b["removed"]
        b["churn"] = b["added"] + b["removed"]
    return series


def author_commit_counts(clone: Path) -> dict:
    raw = git(clone, "log", "--no-merges", "--format=%aN <%aE>")
    counts: dict[str, int] = {}
    for line in raw.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1
    return counts


def _synth_timeline(n: int = 120):
    base = 1262304000  # 2010-01-01T00:00:00Z, 3-day cadence
    for i in range(n):
        yield i, base + i * 3 * 86400


def synthetic_commits(repo_id: str, rows: list, n: int = 120) -> list:
    """Deterministic placeholder commit list (newest first) when no clone is present."""
    authors = sorted(r["author"] for r in rows
                     if r["object_type"] == "repository" and r["author"] != "ALL")
    if not authors:
        authors = ["synthetic <synthetic@example.com>"]
    out = [{"sha": hashlib.sha1(f"{repo_id}:{i}".encode()).hexdigest(),
            "ct": ct, "author": authors[i % len(authors)],
            "subject": f"synthetic commit {i} (no local clone available)"}
           for i, ct in _synth_timeline(n)]
    return list(reversed(out))


def synthetic_series(repo_id: str, rows: list, n: int = 120) -> list:
    """Week-bucketed churn series matching the synthetic commit timeline."""
    buckets: dict[int, dict] = {}
    for i, ct in _synth_timeline(n):
        iso = datetime.fromtimestamp(ct, tz=timezone.utc).isocalendar()
        week_start = datetime.fromisocalendar(iso.year, iso.week, 1).replace(tzinfo=timezone.utc)
        t = int(week_start.timestamp())
        b = buckets.setdefault(t, {"t": t, "added": 0, "removed": 0})
        b["added"] += (i * 7) % 40
        b["removed"] += (i * 3) % 15
    series = sorted(buckets.values(), key=lambda b: b["t"])
    for b in series:
        b["growth"] = b["added"] - b["removed"]
        b["churn"] = b["added"] + b["removed"]
    return series


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "repo-references/*.csv (+ data/repos clones; synthetic commits/series when absent)",
                "repos": []}
    provenance = []
    for spec in REPOS:
        csv_path = ROOT / "repo-references" / spec["csv"]
        if not csv_path.exists():
            print(f"skip {spec['id']}: {csv_path} not found", file=sys.stderr)
            continue
        rows = load_csv(csv_path)
        ref = rows[0]["ref_sha"]
        count = int(rows[0]["commit_count"])
        clone = ROOT / "data" / "repos" / spec["clone_dir"]
        has_clone = (clone / ".git").exists()

        repo_rows = [r for r in rows if r["object_type"] == "repository"]
        all_row = next(r for r in repo_rows if r["author"] == "ALL")
        counts = author_commit_counts(clone) if has_clone else {}
        authors = []
        for r in repo_rows:
            if r["author"] == "ALL":
                continue
            item = {"author": r["author"], **metric_row(r)}
            item["commit_count"] = counts.get(r["author"])
            authors.append(item)
        authors.sort(key=lambda a: (-(a["churn"] or 0), a["author"]))

        detail = {
            "id": spec["id"], "name": spec["name"], "source": spec["source"],
            "ref_sha": ref, "commit_count": count, "status": "ready", "progress": 1.0,
            "authors_count": len(authors),
            "files_count": len({r["path"] for r in rows if r["object_type"] == "file"}),
            "dirs_count": len({r["path"] for r in rows if r["object_type"] == "directory"}),
            "error": None,
        }
        (OUT / f"repo_{spec['id']}.json").write_text(json.dumps(detail, indent=2) + "\n")
        metrics = {
            "object": {"type": "repository", "path": "/"},
            "commit_set": {"count": count, "from": None, "to": None, "commits": None},
            "all": metric_row(all_row),
            "authors": authors,
        }
        (OUT / f"metrics_repository_{spec['id']}.json").write_text(json.dumps(metrics, indent=2) + "\n")
        (OUT / f"children_root_{spec['id']}.json").write_text(
            json.dumps(children_of(rows, ""), indent=2) + "\n")

        if has_clone:
            (OUT / f"commits_{spec['id']}.json").write_text(
                json.dumps(commits_fixture(clone), indent=2) + "\n")
            (OUT / f"series_repository_{spec['id']}.json").write_text(
                json.dumps(weekly_series(clone), indent=2) + "\n")
            commits_source = f"data/repos/{spec['clone_dir']} clone"
        else:
            (OUT / f"commits_{spec['id']}.json").write_text(
                json.dumps(synthetic_commits(spec["id"], rows), indent=2) + "\n")
            (OUT / f"series_repository_{spec['id']}.json").write_text(
                json.dumps(synthetic_series(spec["id"], rows), indent=2) + "\n")
            commits_source = "synthetic (clone absent)"
        entry = {**detail, "commits_source": commits_source,
                 "note": None if has_clone else
                 f"commits/series synthetic: clone data/repos/{spec['clone_dir']} absent"}
        manifest["repos"].append(entry)
        provenance.append((spec["id"], spec["csv"], commits_source))
        print(f"ok {spec['id']}: {len(rows)} csv rows, {len(authors)} authors, clone={has_clone}")

    (OUT / "repos.json").write_text(json.dumps(
        [{k: e[k] for k in ("id", "name", "source", "ref_sha", "commit_count", "status", "progress")}
         for e in manifest["repos"]], indent=2) + "\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    readme = [
        "# fixtures/mock — static Contract C sample data", "",
        "Generated by `python tools/make_fixtures.py` — do not edit by hand.", "",
        "Metrics/authors/children come from `repo-references/*.csv`; the commit picker and",
        "churn series come from the local clones when present, else deterministic synthetic",
        "placeholders (marked below).", "",
        "| repo | metrics source | commits/series source |",
        "| --- | --- | --- |",
    ]
    for repo_id, csv_name, commits_source in provenance:
        readme.append(f"| {repo_id} | repo-references/{csv_name} | {commits_source} |")
    readme += ["", "Regenerate: `python tools/make_fixtures.py` — byte-stable except",
               "`manifest.json.generated_at_utc`.", ""]
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
