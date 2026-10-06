"""Repository ingestion: deep clone + zip upload, both backed by background scans."""
from __future__ import annotations

import re
import shutil
import subprocess
import threading
import zipfile
from pathlib import Path

from rat_engine import scan as engine_scan

from . import catalog

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
REPOS = DATA / "repos"
UPLOADS = DATA / "uploads"
DB = DATA / "db"


class IngestError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "repo"


def _scan_worker(repo_id: str, git_dir: Path, name: str, source: str) -> None:
    def progress(done: int, total: int) -> None:
        catalog.set_status(repo_id, "scanning", progress=(done / total) if total else 0.0)

    try:
        catalog.set_status(repo_id, "scanning", progress=0.0)
        db_path = DB / f"{repo_id}.sqlite"
        meta = engine_scan.scan(git_dir, db_path, name=name, source=source,
                                quiet=True, progress=progress)
        catalog.upsert({
            "id": repo_id, "status": "ready", "progress": 1.0,
            "ref_sha": meta["ref_sha"], "commit_count": meta["commits"],
            "db_path": str(db_path), "git_dir": str(git_dir), "error": None,
        })
    except Exception as exc:  # surface any ingestion/scan failure to the UI
        catalog.set_status(repo_id, "error", progress=0.0, error=str(exc)[:500])


def _start_scan(repo_id: str, git_dir: Path, name: str, source: str) -> None:
    threading.Thread(target=_scan_worker, args=(repo_id, git_dir, name, source),
                     daemon=True).start()


def clone(url: str, name: str | None = None) -> dict:
    url = (url or "").strip()
    if not re.match(r"^(https?://|git@)", url):
        raise IngestError("URL must start with http(s):// or git@")
    if name:
        repo_id = slugify(name)
    else:
        tail = url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        repo_id = slugify(tail[:-4] if tail.endswith(".git") else tail)
    if catalog.get(repo_id) or (REPOS / repo_id).exists():
        raise IngestError(f"repository '{repo_id}' already exists", 409)

    dest = REPOS / repo_id
    catalog.upsert({"id": repo_id, "name": name or repo_id, "source": f"url:{url}",
                    "status": "cloning", "progress": 0.0, "error": None})

    def worker() -> None:
        try:
            REPOS.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--quiet", url, str(dest)],
                           check=True, capture_output=True, text=True, timeout=3600)
            _scan_worker(repo_id, dest, name or repo_id, f"url:{url}")
        except subprocess.TimeoutExpired:
            catalog.set_status(repo_id, "error", error="clone timed out")
        except subprocess.CalledProcessError as exc:
            catalog.set_status(repo_id, "error",
                               error=f"clone failed: {(exc.stderr or '')[:300]}")

    threading.Thread(target=worker, daemon=True).start()
    return catalog.get(repo_id)


def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    for member in archive.namelist():
        target = (dest / member).resolve()
        if not str(target).startswith(str(dest)):
            raise IngestError("zip contains entries outside its root (zip-slip)")
    archive.extractall(dest)


def _find_git_dir(base: Path) -> Path | None:
    if (base / ".git").is_dir():
        return base
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / ".git").is_dir():
            return child
    return None


def upload(data: bytes, filename: str) -> dict:
    stem = Path(filename or "").stem
    repo_id = slugify(stem)
    if not (filename or "").lower().endswith(".zip"):
        raise IngestError("expected a .zip archive containing a git repository")
    if catalog.get(repo_id) or (REPOS / repo_id).exists():
        raise IngestError(f"repository '{repo_id}' already exists", 409)

    UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = REPOS / repo_id
    zip_path = UPLOADS / f"{repo_id}.zip"
    zip_path.write_bytes(data)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            _safe_extract(archive, dest)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise IngestError(f"invalid zip archive: {exc}")

    git_dir = _find_git_dir(dest)
    if git_dir is None:
        shutil.rmtree(dest, ignore_errors=True)
        raise IngestError("no .git directory found inside the uploaded archive")

    catalog.upsert({"id": repo_id, "name": stem, "source": f"zip:{filename}",
                    "status": "scanning", "progress": 0.0, "error": None})
    _start_scan(repo_id, git_dir, stem, f"zip:{filename}")
    return catalog.get(repo_id)


def delete(repo_id: str) -> bool:
    entry = catalog.get(repo_id)
    if not entry:
        return False
    catalog.remove(repo_id)
    shutil.rmtree(REPOS / repo_id, ignore_errors=True)
    for suffix in ("", "-wal", "-shm"):
        p = DB / f"{repo_id}.sqlite{suffix}"
        if p.exists():
            p.unlink()
    return True
