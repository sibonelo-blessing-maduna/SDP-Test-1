"""Engine edge-case tests on the tiny deterministic repo (WS1/WS2 joint gates).

Covers: rename (+edit) attribution, deletion history, binary skip, unicode
author/path, merge-commit exclusion, touch-marker semantics, zip determinism.
"""
import csv
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from fixture_repo import build, zip_repo

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ENV = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}
UNICODE_AUTHOR = "Ólafur Kjartansson <olafur@example.is>"


def _engine(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "rat_engine", *args], env=ENGINE_ENV,
                   capture_output=True, text=True, check=True)


@pytest.fixture(scope="module")
def engine_csv(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("tiny")
    repo = build(tmp)
    db = tmp / "tiny.sqlite"
    out = tmp / "out.csv"
    _engine("scan", "--repo", str(repo), "--name", "tiny", "--db", str(db))
    _engine("export", "--db", str(db), "--out", str(out))
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    table = {(r["object_type"], r["path"], r["author"]): r for r in rows}
    return table, rows


def test_commit_count_excludes_merge(engine_csv):
    _, rows = engine_csv
    assert rows
    assert {r["commit_count"] for r in rows} == {"6"}  # c1..c6, merge excluded


def test_rename_new_path_and_old_history(engine_csv):
    table, _ = engine_csv
    hello = table[("file", "hello.txt", "ALL")]
    assert (hello["added"], hello["removed"]) == ("2", "0")  # c1 only; rename diff -> new path
    moved = table[("file", "src/hello.py", "ALL")]
    assert int(moved["added"]) >= 3  # rename edit + c4 + c6


def test_binary_file_skipped_entirely(engine_csv):
    _, rows = engine_csv
    assert not any(r["path"] == "logo.bin" for r in rows)


def test_unicode_author_and_path(engine_csv):
    table, _ = engine_csv
    assert ("file", "src/hello.py", UNICODE_AUTHOR) in table
    assert ("file", "docs/café.txt", "ALL") in table


def test_deleted_file_rows_survive(engine_csv):
    table, _ = engine_csv
    readme = table[("file", "docs/readme.md", "ALL")]
    assert (readme["added"], readme["removed"]) == ("1", "1")  # add + later deletion


def test_repo_modifications_ignore_binary_only_commit(engine_csv):
    table, _ = engine_csv
    repo_all = table[("repository", "/", "ALL")]
    assert repo_all["modifications"] == "5"  # c1, c2, c4, c5, c6 (c3 = binary only)


def test_zip_structure_and_determinism(tmp_path):
    repo_a = build(tmp_path / "a")
    z1 = zip_repo(repo_a, tmp_path / "a.zip")
    names = zipfile.ZipFile(z1).namelist()
    assert any(n.endswith(".git/HEAD") for n in names)
    assert all(n.startswith("tiny_repo/") for n in names)

    repo_b = build(tmp_path / "b")
    z2 = zip_repo(repo_b, tmp_path / "b.zip")
    assert z1.read_bytes() == z2.read_bytes()
