"""
SQLite connection manager for experiment tracking.

Uses Python's built-in sqlite3 — no extra dependencies required.
WAL mode is enabled for safer concurrent reads/writes.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings

DB_PATH = Path(settings.EXPERIMENTS_DB_PATH)


@contextmanager
def get_db():
    """Yield a SQLite connection; commit on exit, rollback on error."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row          # dict-like access: row["col"]
    conn.execute("PRAGMA journal_mode=WAL") # better concurrent read/write
    conn.execute("PRAGMA foreign_keys=ON")  # enforce FK constraints
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
