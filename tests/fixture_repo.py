#!/usr/bin/env python3
"""Build a tiny deterministic git repo with edge cases, then zip it.

Usage: python tests/fixture_repo.py [--out fixtures/tiny_repo.zip]

Scripted history (fixed dates/authors via env, no reliance on commit SHAs):
  c1  add hello.txt + docs/readme.md            (Alice)
  c2  rename+edit hello.txt -> src/hello.py     (Bob)
  c3  add binary logo.bin                       (Bob)      -> must be skipped by the engine
  c4  edit src/hello.py + add docs/café.txt     (Ólafur)   -> unicode author + path
  c5  delete docs/readme.md                     (Alice)    -> historical rows must survive
  c6  feature branch edits src/hello.py         (Carol)
  m   merge --no-ff feature into main           -> must not be counted (non-merge universe)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "fixtures" / "tiny_repo.zip"

AUTHOR_ALICE = ("Alice Example", "alice@example.com")
AUTHOR_BOB = ("Bob Builder", "bob@example.com")
AUTHOR_OLAFUR = ("Ólafur Kjartansson", "olafur@example.is")
AUTHOR_CAROL = ("Carol Danvers", "carol@example.com")


def _env(author: tuple, date: str) -> dict:
    name, email = author
    return {
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
        "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
    }


def _git(repo: Path, env: dict, *args: str) -> str:
    full = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, **env}
    out = subprocess.run(["git", "-C", str(repo), *args], env=full,
                         capture_output=True, text=True, check=True,
                         encoding="utf-8", errors="replace")
    return out.stdout


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(repo: Path, env: dict, message: str) -> None:
    _git(repo, env, "add", "-A")
    _git(repo, env, "commit", "-q", "-m", message)


def build(workdir: Path) -> Path:
    """Build the repo inside `workdir` (must be empty or absent); returns repo path."""
    repo = workdir / "tiny_repo"
    repo.mkdir(parents=True)
    _git(repo, {}, "init", "-q", "-b", "main")

    # c1: initial content
    _write(repo, "hello.txt", "hello world\nsecond line\n")
    _write(repo, "docs/readme.md", "# tiny\n")
    _commit(repo, _env(AUTHOR_ALICE, "2020-01-01T12:00:00 +0000"), "c1 add hello + readme")

    # c2: rename + edit (rename detection at 50% -> new path src/hello.py)
    (repo / "src").mkdir()
    _git(repo, _env(AUTHOR_BOB, "2020-01-02T12:00:00 +0000"), "mv", "hello.txt", "src/hello.py")
    _write(repo, "src/hello.py", "hello world\nsecond line\nthird line (bob)\n")
    _commit(repo, _env(AUTHOR_BOB, "2020-01-02T12:00:00 +0000"), "c2 rename + edit")

    # c3: binary file (numstat '- -' -> skipped entirely)
    (repo / "logo.bin").write_bytes(b"\x00\x01\x02\x03binary\xff\xfe\x00")
    _commit(repo, _env(AUTHOR_BOB, "2020-01-03T12:00:00 +0000"), "c3 add binary")

    # c4: unicode author + unicode path
    _write(repo, "src/hello.py", "hello world\nsecond line\nthird line (bob)\nfourth (ólafur)\n")
    _write(repo, "docs/café.txt", "café note\n")
    _commit(repo, _env(AUTHOR_OLAFUR, "2020-01-04T12:00:00 +0000"), "c4 unicode author/path")

    # c5: delete (rows must survive deletion)
    (repo / "docs" / "readme.md").unlink()
    _commit(repo, _env(AUTHOR_ALICE, "2020-01-05T12:00:00 +0000"), "c5 delete readme")

    # c6: feature branch + merge (merge excluded from H̄)
    _git(repo, _env(AUTHOR_CAROL, "2020-01-06T12:00:00 +0000"), "checkout", "-q", "-b", "feature")
    _write(repo, "src/hello.py",
           "hello world\nsecond line\nthird line (bob)\nfourth (ólafur)\nfifth (carol)\n")
    _commit(repo, _env(AUTHOR_CAROL, "2020-01-06T13:00:00 +0000"), "c6 feature edit")
    _git(repo, _env(AUTHOR_ALICE, "2020-01-07T12:00:00 +0000"), "checkout", "-q", "main")
    _git(repo, _env(AUTHOR_ALICE, "2020-01-07T13:00:00 +0000"),
         "merge", "-q", "--no-ff", "feature", "-m", "merge feature")
    return repo


def zip_repo(repo: Path, out_zip: Path, arcroot: str = "tiny_repo") -> Path:
    """Zip the repo deterministically (sorted entries, fixed timestamps).

    The git index is skipped: it embeds filesystem stat data (mtime/ctime/inode)
    that changes between builds and would break byte-determinism of the zip.
    History in .git/objects + refs is all the engine needs.
    """
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    skip = {".git/index"}
    files = sorted(p for p in repo.rglob("*")
                   if p.is_file() and p.relative_to(repo).as_posix() not in skip)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            arc = f"{arcroot}/{p.relative_to(repo).as_posix()}"
            info = zipfile.ZipInfo(arc, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, p.read_bytes())
    return out_zip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="tiny_repo_"))
    try:
        repo = build(tmp)
        out = zip_repo(repo, Path(args.out))
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        print(f"built {repo} (HEAD {head[:12]}) -> {out} "
              f"({out.stat().st_size} bytes, {len(list(repo.rglob('*')))} entries)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
