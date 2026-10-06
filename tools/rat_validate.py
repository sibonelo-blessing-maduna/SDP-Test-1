#!/usr/bin/env python3
"""Validate a produced metric CSV against a reference CSV (Contract A).

Usage:
    python tools/rat_validate.py <reference.csv> <produced.csv> \
        [--tol 0] [--ignore-paths a,b/] [--json report.json] [--max-report 50]

Rows are matched on (object_type, path, author). Numeric cells compare as floats
(default tolerance 0 = exact); empty cells compare as empty. Every other column
(repo, ref_sha, commit_set, added..ownership) is compared per row; commit_count is
checked once per file via its distinct-value set. Exit code 1 on any difference.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter

KEY = ("object_type", "path", "author")
NUMERIC = (
    "added", "removed", "growth", "churn", "modifications",
    "modification_frequency", "churn_rate", "ownership",
)
FIELDS = ("repo", "ref_sha", "commit_set", "commit_count") + NUMERIC
# commit_count repeats on every row; compare as a set of distinct values instead.
SET_FIELDS = ("commit_count",)


def load(path: str) -> tuple[dict, list]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    table, dups = {}, []
    for r in rows:
        k = tuple(r.get(c, "") for c in KEY)
        if k in table:
            dups.append(k)
        table[k] = r
    return table, dups


def as_num(s: str):
    s = (s or "").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def cmp_cell(field: str, ref: str, got: str, tol: float) -> bool:
    if field in NUMERIC:
        a, b = as_num(ref), as_num(got)
        if a is None or b is None:
            return (ref or "").strip() == (got or "").strip()
        return abs(a - b) <= tol
    return (ref or "") == (got or "")


def _norm_ignore(ignore_paths) -> set:
    if not ignore_paths:
        return set()
    if isinstance(ignore_paths, str):
        ignore_paths = ignore_paths.split(",")
    return {p.strip() for p in ignore_paths if p and p.strip()}


def _ignored(key: tuple, ignore: set) -> bool:
    path = key[1]
    return any(path == entry or path.startswith(entry) for entry in ignore)


def compare(ref_path: str, got_path: str, tol: float = 0.0,
            ignore_paths=None, max_report: int = 50) -> dict:
    """Diff two metric CSVs; returns a JSON-ready report (see module docstring)."""
    ignore = _norm_ignore(ignore_paths)
    ref, ref_dups = load(ref_path)
    got, got_dups = load(got_path)
    if ignore:
        ref = {k: v for k, v in ref.items() if not _ignored(k, ignore)}
        got = {k: v for k, v in got.items() if not _ignored(k, ignore)}
    ref_keys, got_keys = set(ref), set(got)

    missing = sorted(ref_keys - got_keys)
    extra = sorted(got_keys - ref_keys)
    mismatches = []  # (key, field, ref, got)
    for k in sorted(ref_keys & got_keys):
        for field in FIELDS:
            if field in SET_FIELDS:
                continue
            r, g = ref[k].get(field, ""), got[k].get(field, "")
            if not cmp_cell(field, r, g, tol):
                mismatches.append((k, field, r, g))

    set_field_ok = {}
    for field in SET_FIELDS:
        rv = {ref[k].get(field, "") for k in ref}
        gv = {got[k].get(field, "") for k in got}
        ok = rv == gv
        set_field_ok[field] = {"reference": sorted(rv), "produced": sorted(gv), "ok": ok}
        if not ok:
            mismatches.append((("*", "*", "*"), field, ",".join(sorted(rv)), ",".join(sorted(gv))))

    per_type = Counter(k[0] for k in missing)
    per_type_extra = Counter(k[0] for k in extra)
    mis_by_type = Counter(k[0] for k in (m[0] for m in mismatches))
    mis_by_field = Counter(m[1] for m in mismatches)

    types = sorted({k[0] for k in ref_keys} | {k[0] for k in got_keys})
    per_object_type = {
        t: {
            "rows": {"reference": sum(1 for k in ref_keys if k[0] == t),
                     "produced": sum(1 for k in got_keys if k[0] == t)},
            "missing": per_type.get(t, 0),
            "extra": per_type_extra.get(t, 0),
            "mismatches": mis_by_type.get(t, 0),
        }
        for t in types
    }

    ok = not (missing or extra or mismatches) and all(v["ok"] for v in set_field_ok.values())
    return {
        "ok": ok,
        "reference": ref_path,
        "produced": got_path,
        "tolerance": tol,
        "ignored_prefixes": sorted(ignore),
        "rows": {"reference": len(ref), "produced": len(got)},
        "set_fields": set_field_ok,
        "missing": [list(k) for k in missing],
        "extra": [list(k) for k in extra],
        "mismatches": [
            {"key": list(k), "field": f, "reference": r, "produced": g}
            for k, f, r, g in mismatches
        ],
        "per_object_type": per_object_type,
        "mismatches_by_field": dict(mis_by_field),
        "duplicates": {"reference": len(ref_dups), "produced": len(got_dups)},
    }


def print_report(report: dict, max_report: int = 50) -> None:
    r = report
    cc = r["set_fields"]["commit_count"]
    print(f"reference : {r['reference']}  ({r['rows']['reference']} rows)")
    print(f"produced  : {r['produced']}  ({r['rows']['produced']} rows)")
    print(f"commit_count: ref={cc['reference']} produced={cc['produced']} "
          f"-> {'OK' if cc['ok'] else 'MISMATCH'}")
    if r["tolerance"]:
        print(f"tolerance : {r['tolerance']}")
    if r["ignored_prefixes"]:
        print(f"ignoring  : {r['ignored_prefixes']}")
    if r["duplicates"]["reference"]:
        print(f"WARN duplicate keys in reference: {r['duplicates']['reference']}")
    if r["duplicates"]["produced"]:
        print(f"WARN duplicate keys in produced : {r['duplicates']['produced']}")

    print(f"missing rows : {len(r['missing'])} "
          f"{dict(Counter(k[0] for k in r['missing'])) if r['missing'] else ''}")
    for k in r["missing"][:max_report]:
        print(f"  MISSING {tuple(k)}")
    print(f"extra rows   : {len(r['extra'])} "
          f"{dict(Counter(k[0] for k in r['extra'])) if r['extra'] else ''}")
    for k in r["extra"][:max_report]:
        print(f"  EXTRA   {tuple(k)}")
    print(f"cell mismatches: {len(r['mismatches'])} "
          f"{r['mismatches_by_field'] if r['mismatches'] else ''}")
    for m in r["mismatches"][:max_report]:
        print(f"  MISMATCH {tuple(m['key'])} .{m['field']}: "
              f"ref={m['reference']!r} produced={m['produced']!r}")

    print("per object_type:")
    for t, s in sorted(r["per_object_type"].items()):
        print(f"  {t:<11}: ref={s['rows']['reference']:>6} produced={s['rows']['produced']:>6} "
              f"missing={s['missing']} extra={s['extra']} mismatches={s['mismatches']}")
    print("RESULT:", "EXACT MATCH \u2713" if r["ok"] else "DIFFERENCES FOUND \u2717")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("produced")
    ap.add_argument("--tol", type=float, default=0.0, help="absolute float tolerance (default 0)")
    ap.add_argument("--ignore-paths", default="",
                    help="comma-separated path prefixes to skip (e.g. tests/,docs/readme.md)")
    ap.add_argument("--max-report", type=int, default=50)
    ap.add_argument("--json", dest="json_out", help="write machine-readable report here")
    args = ap.parse_args()

    report = compare(args.reference, args.produced, tol=args.tol,
                     ignore_paths=args.ignore_paths, max_report=args.max_report)
    print_report(report, max_report=args.max_report)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
