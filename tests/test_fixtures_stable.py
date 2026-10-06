"""Acceptance: fixtures/mock regenerates byte-stable (idempotent runs, sorted keys).

manifest.json carries a generated_at_utc timestamp by design; every other file
must be byte-identical across runs.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures" / "mock"


def _run_make_fixtures() -> None:
    subprocess.run([sys.executable, "tools/make_fixtures.py"], cwd=ROOT,
                   check=True, capture_output=True, text=True)


def _snapshot() -> dict:
    return {p.name: p.read_bytes() for p in sorted(FIX.iterdir()) if p.is_file()}


def test_fixtures_regenerate_byte_stable():
    if not FIX.exists():
        pytest.skip("fixtures/mock not generated yet")
    first = _snapshot()
    _run_make_fixtures()
    second = _snapshot()
    assert set(first) == set(second), "file set changed between runs"
    for name in sorted(first):
        if name == "manifest.json":
            a = json.loads(first[name])
            b = json.loads(second[name])
            a.pop("generated_at_utc", None)
            b.pop("generated_at_utc", None)
            assert a == b, "manifest changed (other than generated_at_utc)"
        else:
            assert first[name] == second[name], f"{name} not byte-stable"


def test_fixtures_contract_c_shapes():
    repos = json.loads((FIX / "repos.json").read_text(encoding="utf-8"))
    assert {r["id"] for r in repos} >= {"cjson", "redis", "git"}
    metrics = json.loads((FIX / "metrics_repository_cjson.json").read_text(encoding="utf-8"))
    assert metrics["object"] == {"type": "repository", "path": "/"}
    assert metrics["all"]["added"] == 46377
    assert metrics["authors"][0]["author"] == "Max Bruckner <max@maxbruckner.de>"
    commits = json.loads((FIX / "commits_cjson.json").read_text(encoding="utf-8"))
    assert commits and {"sha", "ct", "author", "subject"} <= set(commits[0])
    series = json.loads((FIX / "series_repository_cjson.json").read_text(encoding="utf-8"))
    assert series and {"t", "added", "removed", "growth", "churn"} <= set(series[0])
    readme = (FIX / "README.md").read_text(encoding="utf-8")
    assert "make_fixtures" in readme
