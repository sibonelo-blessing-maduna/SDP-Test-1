"""FastAPI backend — implements Contract C (contracts/API.md).

Store backend switches on ARCH_MOCK=1: fixture-backed (mockstore) vs the real
SQLite stores written by the rat_engine scanner (data/db/<id>.sqlite).
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import catalog, ingest

ARCH_MOCK = (os.environ.get("ARCH_MOCK") or "").strip().lower() in ("1", "true", "yes", "on")
if ARCH_MOCK:
    from . import mockstore as store
else:
    from . import storeq as store

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"
DB_DIR = ROOT / "data" / "db"
_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

app = FastAPI(title="Repo Analysis Tool API", version="1.0.0",
              description="Contract C — see contracts/API.md")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ingest.IngestError)
async def _ingest_error(_request, exc: ingest.IngestError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


# --- helpers ---------------------------------------------------------------

def _require_repo(repo_id: str) -> dict:
    if not _ID_RE.match(repo_id or ""):
        raise HTTPException(404, f"unknown repository '{repo_id}'")
    if ARCH_MOCK:
        entry = store.repo(repo_id)
    else:
        entry = catalog.get(repo_id)
    if not entry:
        raise HTTPException(404, f"unknown repository '{repo_id}'")
    return entry


@contextmanager
def _store(repo_id: str, write: bool = False):
    """Yield a backend handle: the repo id (mock) or a sqlite connection (real)."""
    entry = _require_repo(repo_id)
    if ARCH_MOCK:
        yield repo_id
        return
    db_path = DB_DIR / f"{repo_id}.sqlite"
    if not db_path.exists():
        status = entry.get("status") or "unknown"
        raise HTTPException(409, f"repository '{repo_id}' is not ready (status: {status})")
    conn = store.connect_rw(db_path) if write else store.connect_ro(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _call(name: str, repo_id: str, *, write: bool = False, **kw):
    with _store(repo_id, write=write) as handle:
        return getattr(store, name)(handle, **kw)


def _filters(from_: int | None, to: int | None, commits: str | None) -> dict:
    if from_ is not None and to is not None and from_ >= to:
        raise HTTPException(422, "'from' must be smaller than 'to'")
    cset = [c.strip() for c in (commits or "").split(",") if c.strip()] or None
    return {"from_ts": from_, "to_ts": to, "commits": cset}


def _base_fields(entry: dict) -> dict:
    return {k: entry.get(k) for k in
            ("id", "name", "source", "ref_sha", "commit_count", "status", "progress")}


# --- repositories ----------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "mode": "mock" if ARCH_MOCK else "store"}


@app.get("/api/repos")
def repos() -> list:
    if ARCH_MOCK:
        return _base_fields_summary()
    return [_base_fields(e) for e in catalog.all()]


def _base_fields_summary() -> list:
    return [_base_fields(e) for e in store.repos()]


@app.get("/api/repos/{repo_id}")
def repo_detail(repo_id: str) -> dict:
    entry = _require_repo(repo_id)
    detail = _base_fields(entry)
    detail.update({"authors_count": None, "files_count": None, "dirs_count": None,
                   "error": entry.get("error")})
    if ARCH_MOCK:
        detail.update({"authors_count": entry.get("authors_count"),
                       "files_count": entry.get("files_count"),
                       "dirs_count": entry.get("dirs_count")})
        return detail
    if entry.get("status") == "ready" and (DB_DIR / f"{repo_id}.sqlite").exists():
        detail.update(_call("repo_counts", repo_id))
    return detail


@app.post("/api/repos/clone", status_code=201)
def repos_clone(payload: dict = Body(...)) -> dict:
    url = (payload or {}).get("url") or ""
    name = (payload or {}).get("name")
    entry = ingest.clone(url, name)
    return {"id": entry["id"], "status": entry.get("status", "scanning")}


@app.post("/api/repos/upload", status_code=201)
async def repos_upload(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    entry = ingest.upload(data, file.filename or "")
    return {"id": entry["id"], "status": entry.get("status", "scanning")}


@app.get("/api/repos/{repo_id}/status")
def repo_status(repo_id: str) -> dict:
    entry = _require_repo(repo_id)
    status = entry.get("status") or "unknown"
    message = entry.get("error") or ("scan complete" if status == "ready" else status)
    return {"status": status, "progress": entry.get("progress") or 0.0, "message": message}


@app.delete("/api/repos/{repo_id}", status_code=204)
def repo_delete(repo_id: str):
    _require_repo(repo_id)
    if ARCH_MOCK:
        raise HTTPException(501, "mock repositories are read-only fixtures")
    ingest.delete(repo_id)
    return None


# --- commits ---------------------------------------------------------------

@app.get("/api/repos/{repo_id}/commits")
def commits(repo_id: str, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
            q: str | None = None, from_: int | None = Query(None, alias="from"),
            to: int | None = Query(None, alias="to")) -> list:
    filters = _filters(from_, to, None)
    return _call("commits_list", repo_id, limit=limit, offset=offset, q=q,
                 from_ts=filters["from_ts"], to_ts=filters["to_ts"])


# --- metrics ---------------------------------------------------------------

@app.get("/api/repos/{repo_id}/metrics")
def metrics(repo_id: str, path: str = Query("/"),
            from_: int | None = Query(None, alias="from"),
            to: int | None = Query(None, alias="to"), commits: str | None = None,
            author: str | None = None) -> dict:
    filters = _filters(from_, to, commits)
    data = _call("object_metrics", repo_id, path=path or "/", author=author, **filters)
    if data is None:
        raise HTTPException(404, f"no metrics for object '{path}'")
    return data


@app.get("/api/repos/{repo_id}/children")
def children(repo_id: str, dir: str = Query("/"), sort: str = "churn", order: str = "desc",
             from_: int | None = Query(None, alias="from"),
             to: int | None = Query(None, alias="to"), commits: str | None = None,
             author: str | None = None) -> list:
    filters = _filters(from_, to, commits)
    return _call("children", repo_id, dir_path=dir or "/", sort=sort, order=order,
                 author=author, **filters)


@app.get("/api/repos/{repo_id}/series")
def series(repo_id: str, path: str = Query("/"), bucket: str = "week",
           from_: int | None = Query(None, alias="from"),
           to: int | None = Query(None, alias="to"), commits: str | None = None) -> list:
    if bucket not in ("day", "week", "month"):
        raise HTTPException(422, "bucket must be one of: day, week, month")
    filters = _filters(from_, to, commits)
    data = _call("series", repo_id, path=path or "/", bucket=bucket, **filters)
    if data is None:
        raise HTTPException(404, f"no series for object '{path}'")
    return data


@app.get("/api/repos/{repo_id}/authors")
def authors(repo_id: str, from_: int | None = Query(None, alias="from"),
            to: int | None = Query(None, alias="to"), commits: str | None = None) -> list:
    filters = _filters(from_, to, commits)
    return _call("repo_authors", repo_id, **filters)


# --- author merging --------------------------------------------------------

@app.post("/api/repos/{repo_id}/authors/merge")
def authors_merge(repo_id: str, payload: dict = Body(...)) -> dict:
    raws = (payload or {}).get("from") or []
    target = (payload or {}).get("to") or ""
    if not isinstance(raws, list) or not raws or not target:
        raise HTTPException(422, "body must be {from: [author, ...], to: author}")
    return {"merges": _call("set_merge", repo_id, write=True, raws=raws, target=target)}


@app.post("/api/repos/{repo_id}/authors/unmerge")
def authors_unmerge(repo_id: str, payload: dict = Body(default={})) -> dict:
    raw = (payload or {}).get("author")
    all_ = bool((payload or {}).get("all"))
    if not raw and not all_:
        raise HTTPException(422, "body must be {author: author} or {all: true}")
    return {"merges": _call("unmerge", repo_id, write=True, raw=raw, all_=all_)}


# --- mailmap ---------------------------------------------------------------

def _mailmap(repo_id: str, apply_: bool) -> dict:
    if ARCH_MOCK:
        entry = _require_repo(repo_id)
        if apply_:
            return store.apply_mailmap(repo_id)
        return store.mailmap_preview(repo_id)
    entry = _require_repo(repo_id)
    git_dir = entry.get("git_dir") or str(ROOT / "data" / "repos" / repo_id)
    with _store(repo_id, write=apply_) as conn:
        if apply_:
            return store.apply_mailmap(conn, git_dir)
        return store.mailmap_preview(conn, git_dir)


@app.get("/api/repos/{repo_id}/mailmap")
def mailmap_preview(repo_id: str) -> dict:
    preview = _mailmap(repo_id, apply_=False)
    return {"available": preview.get("available", False), "entries": preview.get("entries", [])}


@app.post("/api/repos/{repo_id}/mailmap/apply")
def mailmap_apply(repo_id: str) -> dict:
    result = _mailmap(repo_id, apply_=True)
    merges = _call("list_merges", repo_id, write=True)
    return {"merges": merges, "applied": result.get("applied", 0),
            "available": result.get("available", False),
            "entries": result.get("entries", [])}


# --- static frontend (SPA) -------------------------------------------------

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": "Repo Analysis Tool API", "docs": "/docs",
                "frontend": "frontend/dist not built yet"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", "8000")))
