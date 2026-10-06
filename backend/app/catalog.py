"""Repo catalog persisted as data/catalog.json (atomic writes, thread-safe)."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
CATALOG_PATH = DATA / "catalog.json"
_lock = threading.RLock()


def load() -> dict:
    with _lock:
        if not CATALOG_PATH.exists():
            return {}
        try:
            return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}


def _save(cat: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = CATALOG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cat, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, CATALOG_PATH)


def upsert(entry: dict) -> dict:
    with _lock:
        cat = load()
        current = cat.get(entry["id"], {})
        current.update(entry)
        cat[current["id"]] = current
        _save(cat)
        return current


def get(repo_id: str) -> dict | None:
    return load().get(repo_id)


def all() -> list:
    return sorted(load().values(), key=lambda r: r["id"])


def remove(repo_id: str) -> dict | None:
    with _lock:
        cat = load()
        entry = cat.pop(repo_id, None)
        if entry:
            _save(cat)
        return entry


def set_status(repo_id: str, status: str, progress: float | None = None,
               error: str | None = None) -> None:
    update: dict = {"id": repo_id, "status": status}
    if progress is not None:
        update["progress"] = round(progress, 4)
    if error is not None:
        update["error"] = error
    upsert(update)
