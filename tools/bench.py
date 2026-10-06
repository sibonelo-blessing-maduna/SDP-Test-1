#!/usr/bin/env python3
"""Benchmark rat_engine scan + export on a repository (used at S3 against git.git).

Usage: python tools/bench.py --repo data/repos/git [--ref <sha>] [--name git] [--keep-db]

Prints: commit/entry counts, wall time, commits/s and file-entries/s, export
time, CSV rows and size. Exit code 1 if the scan fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ENV = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}


def run_engine(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "rat_engine", *args],
                          env=ENGINE_ENV, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--name", default=None)
    ap.add_argument("--keep-db", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo)
    name = args.name or repo.name
    tmp = Path(tempfile.mkdtemp(prefix="rat_bench_"))
    db = tmp / "bench.sqlite"
    csv_out = tmp / "bench.csv"

    t0 = time.time()
    scan = run_engine("scan", "--repo", str(repo), "--name", name,
                      "--db", str(db), "--ref", args.ref)
    scan_s = time.time() - t0
    if scan.returncode != 0:
        print(scan.stderr.strip()[:2000], file=sys.stderr)
        print("BENCH FAILED (scan)", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db)
    commits = conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    files = conn.execute("SELECT COUNT(*) FROM file_stats").fetchone()[0]
    dirs = conn.execute("SELECT COUNT(*) FROM dir_stats").fetchone()[0]
    conn.close()

    t1 = time.time()
    exp = run_engine("export", "--db", str(db), "--out", str(csv_out))
    export_s = time.time() - t1
    if exp.returncode != 0:
        print(exp.stderr.strip()[:2000], file=sys.stderr)
        print("BENCH FAILED (export)", file=sys.stderr)
        return 1

    with open(csv_out, encoding="utf-8") as f:
        rows = sum(1 for _ in f) - 1
    size = csv_out.stat().st_size

    result = {
        "repo": str(repo.resolve()), "name": name,
        "commits": commits, "file_entries": files, "dir_entries": dirs,
        "scan_seconds": round(scan_s, 2),
        "commits_per_s": round(commits / scan_s, 1) if scan_s else None,
        "file_entries_per_s": round(files / scan_s, 1) if scan_s else None,
        "export_seconds": round(export_s, 2),
        "csv_rows": rows, "csv_bytes": size,
    }
    print(json.dumps(result, indent=2))

    if args.keep_db:
        kept = ROOT / "data" / "bench" / f"{name}.sqlite"
        kept.parent.mkdir(parents=True, exist_ok=True)
        os.replace(db, kept)
        print(f"db kept at {kept}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
