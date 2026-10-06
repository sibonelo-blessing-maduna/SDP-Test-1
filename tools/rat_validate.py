#!/usr/bin/env python3
"""Validate a produced metric CSV against a reference CSV (Contract A).

Usage:
    python tools/rat_validate.py <reference.csv> <produced.csv> [--tol 0] [--json report.json]

Rows are matched on (object_type, path, author). Numeric cells compare as floats
(default tolerance 0 = exact); empty cells compare as empty. Exit code 1 on any diff.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter

KEY = ("object_type", "path", "author")
NUMERIC = (
    "commit_count", "added", "removed", "growth", "churn", "modifications",
    "modification_frequency", "churn_rate", "ownership",
)


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("produced")
    ap.add_argument("--tol", type=float, default=0.0, help="absolute float tolerance (default 0)")
    ap.add_argument("--max-report", type=int, default=50)
    ap.add_argument("--json", dest="json_out", help="write machine-readable report here")
    args = ap.parse_args()

    ref, ref_dups = load(args.reference)
    got, got_dups = load(args.produced)
    ref_keys, got_keys = set(ref), set(got)

    missing = sorted(ref_keys - got_keys)
    extra = sorted(got_keys - ref_keys)
    mismatches = []  # (key, field, ref, got)
    for k in sorted(ref_keys & got_keys):
        for field in NUMERIC:
            r, g = ref[k].get(field, ""), got[k].get(field, "")
            if not cmp_cell(field, r, g, args.tol):
                mismatches.append((k, field, r, g))

    # commit_count is a repo-level value repeated on every row; check once, not per row
    mismatches = [m for m in mismatches if m[1] != "commit_count"]
    cc_ref = next((ref[k]["commit_count"] for k in ref if "commit_count" in ref[k]), None)
    cc_got = next((got[k]["commit_count"] for k in got if "commit_count" in got[k]), None)
    cc_ok = (cc_ref == cc_got)

    per_type = Counter(k[0] for k in missing)
    per_type_extra = Counter(k[0] for k in extra)
    per_type_mis = Counter(k[0] for _, k, _, _ in mismatches)

    ok = not (missing or extra or mismatches) and cc_ok
    print(f"reference : {args.reference}  ({len(ref)} rows)")
    print(f"produced  : {args.produced}  ({len(got)} rows)")
    print(f"commit_count: ref={cc_ref} produced={cc_got} -> {'OK' if cc_ok else 'MISMATCH'}")
    if ref_dups:
        print(f"WARN duplicate keys in reference: {len(ref_dups)}")
    if got_dups:
        print(f"WARN duplicate keys in produced : {len(got_dups)}")
    print(f"missing rows : {len(missing)} {dict(per_type) if missing else ''}")
    for k in missing[: args.max_report]:
        print(f"  MISSING {k}")
    print(f"extra rows   : {len(extra)} {dict(per_type_extra) if extra else ''}")
    for k in extra[: args.max_report]:
        print(f"  EXTRA   {k}")
    print(f"cell mismatches: {len(mismatches)} {dict(per_type_mis) if mismatches else ''}")
    for k, field, r, g in mismatches[: args.max_report]:
        print(f"  MISMATCH {k} .{field}: ref={r!r} produced={g!r}")
    print("RESULT:", "EXACT MATCH \u2713" if ok else "DIFFERENCES FOUND \u2717")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ok": ok,
                    "reference": args.reference,
                    "produced": args.produced,
                    "rows": {"reference": len(ref), "produced": len(got)},
                    "commit_count": {"reference": cc_ref, "produced": cc_got, "ok": cc_ok},
                    "missing": [list(k) for k in missing],
                    "extra": [list(k) for k in extra],
                    "mismatches": [
                        {"key": list(k), "field": f, "reference": r, "produced": g}
                        for k, f, r, g in mismatches
                    ],
                },
                f,
                indent=2,
            )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
