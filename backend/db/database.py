"""
backend/db/database.py
──────────────────────
SQLite connection factory for the Screenshot Knowledge Base.

Usage
─────
    from backend.db.database import get_connection

    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM images").fetchall()
        # rows[0]["filename"] — dict-style access via dict_row_factory

Design notes
────────────
* WAL journal mode   — allows concurrent readers while a writer is active.
* foreign_keys = ON  — enforces FK constraints (OFF is SQLite's default).
* synchronous = NORMAL — good durability/performance balance under WAL.
* dict_row_factory   — every row is returned as a plain dict for easy
                        serialisation to JSON / Pydantic models.
* create_all_tables  — called once per connection; the schema DDL uses
                       IF NOT EXISTS so it's cheap after the first run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from backend.config import DATABASE
from backend.db.schema import create_all_tables


# ─────────────────────────────────────────────────────────────────────────────
# Row factory
# ─────────────────────────────────────────────────────────────────────────────

def dict_row_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    """Return each row as a :class:`dict` keyed by column name.

    Assigned to ``sqlite3.Connection.row_factory`` so that
    ``conn.execute(...).fetchall()`` returns ``list[dict]`` instead of
    ``list[tuple]``.

    Args:
        cursor: The active :class:`sqlite3.Cursor` whose ``description``
                provides column names.
        row:    The raw row tuple from SQLite.

    Returns:
        A plain Python dict mapping column name → value.
    """
    return {col[0]: value for col, value in zip(cursor.description, row)}


# ─────────────────────────────────────────────────────────────────────────────
# Connection factory
# ─────────────────────────────────────────────────────────────────────────────

def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open (and initialise) a SQLite connection to the knowledge-base.

    The function:
      1. Resolves *db_path* (defaults to :data:`backend.config.DATABASE`).
      2. Creates parent directories if they don't exist.
      3. Opens the database with the recommended PRAGMA settings.
      4. Calls :func:`backend.db.schema.create_all_tables` to ensure the
         schema is up-to-date (idempotent).
      5. Returns the ready-to-use :class:`sqlite3.Connection`.

    The connection is intentionally **not** used as a context manager here so
    callers control transaction boundaries explicitly.  Wrap it in a
    ``with conn:`` block to get auto-commit/rollback, or close manually.

    Args:
        db_path: Optional override for the database file path.  Accepts a
                 :class:`pathlib.Path` or a plain string.  Defaults to
                 :data:`backend.config.DATABASE`.

    Returns:
        A configured :class:`sqlite3.Connection` with ``dict_row_factory``
        set and all application tables created.

    Example::

        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO images (filename, ...) VALUES (?, ...)", (...)
                )
        finally:
            conn.close()
    """
    resolved: Path = Path(db_path) if db_path is not None else DATABASE

    # Ensure the parent directory exists (e.g. data/ on first run)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(resolved), check_same_thread=False)

    # ── Attach dict row factory ───────────────────────────────────────────────
    conn.row_factory = dict_row_factory  # type: ignore[assignment]

    # ── PRAGMA configuration ──────────────────────────────────────────────────
    conn.execute("PRAGMA journal_mode = WAL;")        # concurrent reads + write
    conn.execute("PRAGMA foreign_keys = ON;")         # enforce FK constraints
    conn.execute("PRAGMA synchronous = NORMAL;")      # safe under WAL, faster than FULL

    # ── Bootstrap schema ──────────────────────────────────────────────────────
    create_all_tables(conn)

    return conn
