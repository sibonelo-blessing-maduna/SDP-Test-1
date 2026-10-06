"""Mutation-detection proof for tools/rat_validate.py.

Injects every single-cell mutation into copies of (a) a small synthetic
reference and (b) a sample of the real cJSON reference, and asserts 100%
detection. Also guards against false positives and exercises --tol.
"""
import csv
import random
from pathlib import Path

import pytest

from rat_validate import compare

ROOT = Path(__file__).resolve().parent.parent
HEADER = ["repo", "ref_sha", "commit_set", "commit_count", "object_type", "path",
          "author", "added", "removed", "growth", "churn", "modifications",
          "modification_frequency", "churn_rate", "ownership"]
KEYS = ("object_type", "path", "author")
INT_FIELDS = {"commit_count", "added", "removed", "growth", "churn", "modifications"}
FLOAT_FIELDS = {"modification_frequency", "churn_rate", "ownership"}
CELL_FIELDS = [f for f in HEADER if f not in KEYS]

SAMPLE = [
    {"repo": "small", "ref_sha": "a" * 40, "commit_set": "all", "commit_count": "10",
     "object_type": "repository", "path": "/", "author": "ALL",
     "added": "100", "removed": "40", "growth": "60", "churn": "140",
     "modifications": "9", "modification_frequency": "0.9", "churn_rate": "14.0",
     "ownership": ""},
    {"repo": "small", "ref_sha": "a" * 40, "commit_set": "all", "commit_count": "10",
     "object_type": "directory", "path": "docs", "author": "ALL",
     "added": "7", "removed": "1", "growth": "6", "churn": "8",
     "modifications": "2", "modification_frequency": "0.2", "churn_rate": "0.8",
     "ownership": ""},
    {"repo": "small", "ref_sha": "a" * 40, "commit_set": "all", "commit_count": "10",
     "object_type": "file", "path": "docs/readme.md", "author": "ALL",
     "added": "7", "removed": "1", "growth": "6", "churn": "8",
     "modifications": "2", "modification_frequency": "0.2", "churn_rate": "0.8",
     "ownership": ""},
    {"repo": "small", "ref_sha": "a" * 40, "commit_set": "all", "commit_count": "10",
     "object_type": "file", "path": "docs/readme.md", "author": "Alice <a@x>",
     "added": "7", "removed": "1", "growth": "6", "churn": "8",
     "modifications": "2", "modification_frequency": "", "churn_rate": "",
     "ownership": "1.0"},
    {"repo": "small", "ref_sha": "a" * 40, "commit_set": "all", "commit_count": "10",
     "object_type": "file", "path": "docs/gone.txt", "author": "ALL",
     "added": "0", "removed": "0", "growth": "0", "churn": "0",
     "modifications": "0", "modification_frequency": "0.0", "churn_rate": "0.0",
     "ownership": ""},
    {"repo": "small", "ref_sha": "a" * 40, "commit_set": "all", "commit_count": "10",
     "object_type": "file", "path": "docs/gone.txt", "author": "Bob <b@x>",
     "added": "3", "removed": "0", "growth": "3", "churn": "3",
     "modifications": "1", "modification_frequency": "", "churn_rate": "",
     "ownership": "0.30000000000000004"},
]


def write_csv(path: Path, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)


def mutate(value: str, field: str) -> str:
    """A deterministic, semantics-changing single-cell mutation."""
    if field in INT_FIELDS:
        return str(int(value) + 1) if value.strip() else "1"
    if field in FLOAT_FIELDS:
        return f"{float(value) + 0.25!r}" if value.strip() else "0.125"
    return value + "X"


@pytest.fixture()
def ref_file(tmp_path):
    ref = tmp_path / "ref.csv"
    write_csv(ref, SAMPLE)
    return ref


def test_no_false_positive(ref_file, tmp_path):
    copy = tmp_path / "copy.csv"
    write_csv(copy, SAMPLE)
    report = compare(str(ref_file), str(copy))
    assert report["ok"] is True, report


def test_every_single_cell_mutation_detected(ref_file, tmp_path):
    total = detected = 0
    for row_idx in range(len(SAMPLE)):
        for field in CELL_FIELDS:
            rows = [dict(r) for r in SAMPLE]
            rows[row_idx][field] = mutate(rows[row_idx][field], field)
            mutated = tmp_path / "mutated.csv"
            write_csv(mutated, rows)
            report = compare(str(ref_file), str(mutated))
            total += 1
            if not report["ok"]:
                detected += 1
            else:
                pytest.fail(f"undetected mutation: row={row_idx} field={field}")
    assert total == len(SAMPLE) * len(CELL_FIELDS)
    assert detected == total


def test_key_mutation_detected(ref_file, tmp_path):
    rows = [dict(r) for r in SAMPLE]
    rows[3]["path"] = "docs/other.md"
    mutated = tmp_path / "key.csv"
    write_csv(mutated, rows)
    report = compare(str(ref_file), str(mutated))
    assert report["ok"] is False
    assert report["missing"] and report["extra"]


def test_tolerance_semantics(ref_file, tmp_path):
    rows = [dict(r) for r in SAMPLE]
    rows[2]["churn_rate"] = repr(float(rows[2]["churn_rate"]) + 1e-12)
    near = tmp_path / "near.csv"
    write_csv(near, rows)
    assert compare(str(ref_file), str(near))["ok"] is False
    assert compare(str(ref_file), str(near), tol=1e-9)["ok"] is True


def test_ignore_paths(tmp_path):
    ref = tmp_path / "ref.csv"
    got = tmp_path / "got.csv"
    write_csv(ref, SAMPLE)
    rows = [dict(r) for r in SAMPLE]
    rows[2]["added"] = "999"  # docs/ directory row mutated
    write_csv(got, rows)
    assert compare(str(ref), str(got))["ok"] is False
    assert compare(str(ref), str(got), ignore_paths="docs")["ok"] is True


def test_real_cjson_reference_sampled_mutations(tmp_path):
    ref_path = ROOT / "repo-references" / "cJSON_6d9f2443ab07.csv"
    if not ref_path.exists():
        pytest.skip("cJSON reference CSV missing")
    with open(ref_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rng = random.Random(42)
    cells = [(rng.randrange(len(rows)), rng.choice(CELL_FIELDS)) for _ in range(150)]
    detected = 0
    for row_idx, field in cells:
        mutated_rows = [dict(r) for r in rows]
        mutated_rows[row_idx][field] = mutate(mutated_rows[row_idx][field], field)
        out = tmp_path / "mutated.csv"
        write_csv(out, mutated_rows)
        if not compare(str(ref_path), str(out))["ok"]:
            detected += 1
    assert detected == len(cells)
