"""Streaming scanner: git history -> Contract B store.

Pinned recipe (see contracts/ENGINE_OUTPUT.md §2):
    git log --no-merges --numstat -z -M50% --format='<US>%H..%ct..%an <%ae>..%s' <ref>
NUL-separated wire format:
  * commit header: text line, fields separated by \\x1f, sentinel \\x02 at start
  * entries: b"<added>\\t<removed>\\t<path>" bested by NUL
  * renames: b"<added>\\t<removed>\\t" + NUL + old + NUL + new   (attribute to NEW path)
  * binaries: b"-\\t-\\t..."  -> skipped
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, store

SENTINEL = b"\x02"
FIELD_SEP = b"\x1f"
LOG_FORMAT = "%x02%H%x1f%ct%x1f%an <%ae>%x1f%s"


def resolve_ref(repo, ref: str = "HEAD") -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True,
    )
    if out.returncode != 0:
        raise SystemExit(f"git rev-parse failed for {ref!r}: {out.stderr.decode(errors='replace').strip()}")
    return out.stdout.decode().strip()


def _parse_piece(piece: bytes):
    """Parse one sentinel-delimited commit piece -> (commit, entries) or None."""
    if not piece:
        return None
    parts = piece.split(b"\x00")
    head = parts[0]
    nl = head.find(b"\n")
    header_line, rest = (head, b"") if nl < 0 else (head[:nl], head[nl + 1:])
    if header_line.startswith(b"\n"):
        header_line = header_line[1:]
    fields = header_line.split(FIELD_SEP)
    if len(fields) != 4:
        return None
    sha, ct, author, subject = fields
    commit = {
        "sha": sha.decode("utf-8", "surrogateescape"),
        "ct": int(ct),
        "author": author.decode("utf-8", "surrogateescape"),
        "subject": subject.decode("utf-8", "surrogateescape"),
    }
    chunks = ([rest] if rest else []) + parts[1:]
    entries = []
    i, n = 0, len(chunks)
    while i < n:
        ch = chunks[i]
        if not ch:
            i += 1
            continue
        if ch.startswith(b"\n"):
            ch = ch[1:]
            if not ch:
                i += 1
                continue
        f = ch.split(b"\t", 2)
        if len(f) != 3:
            i += 1
            continue
        added_b, removed_b, path_b = f
        if path_b == b"":
            # rename entry: next two chunks are old path, new path
            if i + 2 >= n:
                break
            new_b = chunks[i + 2]
            i += 3
        else:
            new_b = path_b
            i += 1
        if added_b == b"-":  # binary: not measured
            continue
        try:
            added, removed = int(added_b), int(removed_b)
        except ValueError:
            continue
        # 0/0 entries (pure renames) are kept as touch markers: they create the object
        # (all-zero ALL row) but contribute no author rows (enforced in metrics).
        entries.append((added, removed, new_b.decode("utf-8", "surrogateescape")))
    return commit, entries


def iter_stream(stream, chunk_size: int = 1 << 20):
    """Yield (commit, entries) from a `git log ... -z` byte stream."""
    buf = b""
    while True:
        block = stream.read(chunk_size)
        if not block:
            break
        buf += block
        if SENTINEL not in buf:
            continue
        pieces = buf.split(SENTINEL)
        buf = pieces.pop()  # last piece may be incomplete
        for piece in pieces:
            parsed = _parse_piece(piece)
            if parsed:
                yield parsed
    for piece in buf.split(SENTINEL):
        parsed = _parse_piece(piece)
        if parsed:
            yield parsed


def _ancestors(path: str) -> list:
    """Ancestor directories of a file path, including root '/', shallowest first."""
    parts = path.split("/")[:-1]
    dirs, cur = [], ""
    for part in parts:
        cur = part if not cur else f"{cur}/{part}"
        dirs.append(cur)
    dirs.append("/")
    return dirs


def _flush(conn, commits: list, files: list, dirs: list) -> None:
    conn.executemany("INSERT OR REPLACE INTO commits(sha, ct, author, subject) VALUES (?,?,?,?)", commits)
    conn.executemany("INSERT OR REPLACE INTO file_stats(sha, path, added, removed) VALUES (?,?,?,?)", files)
    conn.executemany("INSERT OR REPLACE INTO dir_stats(sha, path, added, removed) VALUES (?,?,?,?)", dirs)
    conn.commit()


def scan(repo, db, name: str | None = None, ref: str = "HEAD",
         source: str | None = None, quiet: bool = False) -> dict:
    t0 = time.time()
    repo = Path(repo)
    ref_sha = resolve_ref(repo, ref)
    conn = store.connect(db)
    store.reset(conn)

    cmd = ["git", "-C", str(repo), "log", "--no-merges", "--numstat", "-z", "-M50%",
           f"--format={LOG_FORMAT}", ref_sha]
    errf = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf)

    n_commits = n_files = n_dirs = 0
    pending_c, pending_f, pending_d = [], [], []
    last_report = t0
    for commit, entries in iter_stream(proc.stdout):
        n_commits += 1
        pending_c.append((commit["sha"], commit["ct"], commit["author"], commit["subject"]))
        files, dirs = {}, {}
        for added, removed, path in entries:
            a, r = files.get(path, (0, 0))
            files[path] = (a + added, r + removed)
            for d in _ancestors(path):
                da, dr = dirs.get(d, (0, 0))
                dirs[d] = (da + added, dr + removed)
        sha = commit["sha"]
        for path, (a, r) in files.items():
            pending_f.append((sha, path, a, r))
        for d, (a, r) in dirs.items():
            pending_d.append((sha, d, a, r))
        if len(pending_f) >= 20000:
            _flush(conn, pending_c, pending_f, pending_d)
            n_files += len(pending_f)
            n_dirs += len(pending_d)
            pending_c, pending_f, pending_d = [], [], []
            if not quiet and time.time() - last_report > 1.0:
                rate = n_commits / max(time.time() - t0, 1e-9)
                print(f"  scan: {n_commits} commits, {n_files} file-entries "
                      f"({rate:.0f} commits/s)", file=sys.stderr)
                last_report = time.time()
    _flush(conn, pending_c, pending_f, pending_d)
    n_files += len(pending_f)
    n_dirs += len(pending_d)

    rc = proc.wait()
    if rc != 0:
        errf.seek(0)
        err = errf.read().decode(errors="replace").strip()
        errf.close()
        raise SystemExit(f"git log failed ({rc}): {err[:500]}")
    errf.close()

    store.set_meta(conn, {
        "name": name or repo.name,
        "git_dir": str(repo.resolve()),
        "ref_sha": ref_sha,
        "commit_count": n_commits,
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine_version": __version__,
        "rename_mode": "-M50%",
        **({"source": source} if source else {}),
    })
    store.log(conn, "info", f"scanned {n_commits} commits, {n_files} file-entries, "
                            f"{n_dirs} dir-entries in {time.time() - t0:.1f}s")
    summary = {"commits": n_commits, "file_entries": n_files, "dir_entries": n_dirs,
               "seconds": round(time.time() - t0, 2), "ref_sha": ref_sha}
    if not quiet:
        print(f"  scan done: {summary}", file=sys.stderr)
    return summary
