"""Contract C tests (pytest + httpx TestClient).

Runs green against the mock store (ARCH_MOCK=1, fixtures/mock) and — once the
real stores exist — against the real store (data/db/cjson.sqlite, built by
tools/validate_all.sh). Reference values come from repo-references/.
"""
import importlib
import io
import os
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent.parent
REAL_DB = ROOT / "data" / "db" / "cjson.sqlite"
REF_SHA = "6d9f2443ab071f86e5d9b43025a40929ec41c46c"

# cJSON reference totals (repository ALL row).
REF = {"added": 46377, "removed": 11211, "growth": 35166, "churn": 57588,
       "modifications": 953, "commit_count": 955}
MAX_AUTHOR = "Max Bruckner <max@maxbruckner.de>"


def _client(mock: bool) -> TestClient:
    if mock:
        os.environ["ARCH_MOCK"] = "1"
    else:
        os.environ.pop("ARCH_MOCK", None)
    from app import main

    importlib.reload(main)
    return TestClient(main.app)


@pytest.fixture(scope="module")
def mock_client():
    return _client(mock=True)


@pytest.fixture(scope="module")
def real_client():
    if not REAL_DB.exists():
        pytest.skip("real store not built yet (run tools/validate_all.sh)")
    from app import catalog

    entry = catalog.get("cjson") or {}
    if entry.get("status") != "ready":
        catalog.upsert({"id": "cjson", "name": "cJSON",
                        "source": "url:https://github.com/DaveGamble/cJSON.git",
                        "status": "ready", "progress": 1.0, "ref_sha": REF_SHA,
                        "commit_count": REF["commit_count"],
                        "db_path": str(REAL_DB)})
    return _client(mock=False)


def _check_metrics_root(client: TestClient) -> None:
    r = client.get("/api/repos/cjson/metrics")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["object"] == {"type": "repository", "path": "/"}
    assert data["commit_set"]["count"] == REF["commit_count"]
    all_ = data["all"]
    for key in ("added", "removed", "growth", "churn", "modifications"):
        assert all_[key] == REF[key], key
    assert all_["ownership"] is None
    assert all_["modification_frequency"] == pytest.approx(953 * (1.0 / 955), rel=1e-9)
    assert all_["churn_rate"] == pytest.approx(57588 * (1.0 / 955), rel=1e-9)
    authors = data["authors"]
    assert authors and authors[0]["author"] == MAX_AUTHOR
    assert authors[0]["added"] == 39192
    assert authors[0]["ownership"] == pytest.approx(0.83684, abs=1e-4)
    assert authors[0]["modification_frequency"] is None
    assert authors[0]["churn_rate"] is None


# --- mock store ------------------------------------------------------------

def test_health_mock(mock_client):
    r = mock_client.get("/api/health")
    assert r.status_code == 200 and r.json()["mode"] == "mock"


def test_repos_list_mock(mock_client):
    r = mock_client.get("/api/repos")
    assert r.status_code == 200
    repos = r.json()
    assert {p["id"] for p in repos} >= {"cjson", "redis", "git"}
    assert all({"id", "name", "source", "status", "progress"} <= set(p) for p in repos)


def test_repo_detail_mock(mock_client):
    r = mock_client.get("/api/repos/cjson")
    assert r.status_code == 200
    detail = r.json()
    assert detail["authors_count"] == 107
    assert detail["files_count"] == 245
    assert detail["dirs_count"] == 45
    assert detail["status"] == "ready"


def test_unknown_repo_404(mock_client):
    assert mock_client.get("/api/repos/nope").status_code == 404
    assert mock_client.get("/api/repos/nope/metrics").status_code == 404


def test_metrics_root_mock(mock_client):
    _check_metrics_root(mock_client)


def test_metrics_unknown_object_404(mock_client):
    r = mock_client.get("/api/repos/cjson/metrics", params={"path": "no/such/file.c"})
    assert r.status_code == 404


def test_bad_range_422(mock_client):
    r = mock_client.get("/api/repos/cjson/metrics",
                        params={"from": 200, "to": 100})
    assert r.status_code == 422


def test_children_mock(mock_client):
    r = mock_client.get("/api/repos/cjson/children")
    assert r.status_code == 200
    items = r.json()
    assert items and {"name", "path", "type", "churn"} <= set(items[0])
    churns = [i["churn"] for i in items]
    assert churns == sorted(churns, reverse=True)


def test_series_mock(mock_client):
    r = mock_client.get("/api/repos/cjson/series")
    assert r.status_code == 200
    pts = r.json()
    assert pts and {"t", "added", "removed", "growth", "churn"} <= set(pts[0])
    assert [p["t"] for p in pts] == sorted(p["t"] for p in pts)
    r = mock_client.get("/api/repos/cjson/series", params={"bucket": "fortnight"})
    assert r.status_code == 422


def test_commits_mock(mock_client):
    r = mock_client.get("/api/repos/cjson/commits", params={"limit": 5})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 5
    assert {"sha", "ct", "author", "subject"} <= set(rows[0])
    r = mock_client.get("/api/repos/cjson/commits", params={"q": "Max Bruckner"})
    assert r.status_code == 200
    assert r.json() and all("Max Bruckner" in c["author"] for c in r.json())


def test_authors_mock(mock_client):
    r = mock_client.get("/api/repos/cjson/authors")
    assert r.status_code == 200
    rows = r.json()
    assert rows and {"author", "churn", "commit_count", "ownership"} <= set(rows[0])
    total = sum(a["ownership"] for a in rows)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_merge_unmerge_mock(mock_client):
    r = mock_client.post("/api/repos/cjson/authors/merge",
                         json={"from": ["Old Name <old@x>"], "to": MAX_AUTHOR})
    assert r.status_code == 200
    assert r.json()["merges"]["Old Name <old@x>"] == MAX_AUTHOR
    r = mock_client.post("/api/repos/cjson/authors/unmerge", json={"all": True})
    assert r.status_code == 200 and r.json()["merges"] == {}


def test_status_endpoint(mock_client):
    r = mock_client.get("/api/repos/cjson/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready" and body["progress"] == 1.0


def test_upload_rejects_garbage(mock_client):
    r = mock_client.post("/api/repos/upload",
                         files={"file": ("garbage.zip", io.BytesIO(b"not a zip"), "application/zip")})
    assert r.status_code == 400
    assert "zip" in r.json()["detail"].lower() or "archive" in r.json()["detail"].lower()


# --- real store ------------------------------------------------------------

def test_metrics_root_real(real_client):
    _check_metrics_root(real_client)


def test_children_real(real_client):
    r = real_client.get("/api/repos/cjson/children")
    assert r.status_code == 200
    items = r.json()
    assert items
    assert all(i["type"] in ("dir", "file") for i in items)
    assert all(i["path"].count("/") <= 1 for i in items)


def test_series_real(real_client):
    r = real_client.get("/api/repos/cjson/series", params={"bucket": "month"})
    assert r.status_code == 200 and r.json()


def test_commits_real(real_client):
    r = real_client.get("/api/repos/cjson/commits", params={"limit": 3})
    assert r.status_code == 200 and len(r.json()) == 3


def test_merge_overlay_real(real_client):
    from app import catalog  # noqa: F401  (ensures module import order is fine)

    r = real_client.post("/api/repos/cjson/authors/merge",
                         json={"from": ["Ghost <ghost@void>"], "to": MAX_AUTHOR})
    assert r.status_code == 200
    assert r.json()["merges"].get("Ghost <ghost@void>") == MAX_AUTHOR
    r = real_client.post("/api/repos/cjson/authors/unmerge", json={"all": True})
    assert r.status_code == 200 and r.json()["merges"] == {}


def test_not_ready_409(real_client):
    from app import catalog

    catalog.upsert({"id": "pending-repo", "name": "pending", "status": "cloning",
                    "progress": 0.1, "source": "url:x"})
    try:
        r = real_client.get("/api/repos/pending-repo/metrics")
        assert r.status_code == 409
    finally:
        catalog.remove("pending-repo")
