"""rat_engine — Repo Analysis Tool metric engine (WS1).

Pure-stdlib git scanner + SQLite store + Contract A CSV exporter.

Run from ``backend/`` (or with ``PYTHONPATH=backend``)::

    python -m rat_engine scan   --repo <path> --name <name> --db <store.sqlite>
    python -m rat_engine export --db <store.sqlite> [--out file.csv]
"""

__version__ = "0.1.0"
