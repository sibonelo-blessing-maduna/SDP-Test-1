"""CLI entry point: python -m rat_engine {scan,export}  (Contract A §3)."""
from __future__ import annotations

import argparse
import sys

from . import metrics, store
from . import scan as scan_mod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rat_engine", description="RAT metric engine (WS1)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="walk git history into the SQLite store (Contract B)")
    s.add_argument("--repo", required=True, help="path to a git repository")
    s.add_argument("--db", required=True, help="store path (data/db/<id>.sqlite)")
    s.add_argument("--name", help="repository label used in exports (default: dir name)")
    s.add_argument("--ref", default="HEAD", help="reference commit (default HEAD)")
    s.add_argument("--source", help="provenance, e.g. url:<url> or zip:<file>")

    e = sub.add_parser("export", help="write metric CSV (Contract A) to stdout")
    e.add_argument("--db", required=True)
    e.add_argument("--out", help="write to a file instead of stdout")
    e.add_argument("--ref", help="expected ref (sha or prefix); errors if store differs")
    e.add_argument("--from", dest="from_ts", type=int, help="committer time >= (unix sec)")
    e.add_argument("--to", dest="to_ts", type=int, help="committer time < (unix sec)")
    e.add_argument("--commits", help="comma-separated sha list (overrides --from/--to)")
    e.add_argument("--author", help="only rows for this author (plus ALL rows)")
    e.add_argument("--object", dest="object_path", help="only this object ('/' = repository)")

    args = ap.parse_args(argv)
    if args.cmd == "scan":
        scan_mod.scan(args.repo, args.db, name=args.name, ref=args.ref, source=args.source)
        return 0

    conn = store.connect(args.db)
    meta = store.get_meta(conn)
    if not meta.get("ref_sha"):
        sys.exit(f"store {args.db} is empty — run `rat_engine scan` first")
    if args.ref:
        want = args.ref.strip()
        if not meta["ref_sha"].startswith(want):
            sys.exit(f"store holds ref {meta['ref_sha']}, requested {want} — rescan required")

    commits = [c.strip() for c in args.commits.split(",")] if args.commits else None
    rows = metrics.export_rows(conn, from_ts=args.from_ts, to_ts=args.to_ts,
                               commits=commits, author=args.author,
                               object_path=args.object_path)
    from .export import write_csv

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            write_csv(rows, fh)
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        write_csv(rows, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
