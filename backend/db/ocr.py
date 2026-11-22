"""
backend/db/ocr.py
─────────────────
Database access layer for OCR operations.

Provides thin, well-tested helpers that sit between the OCR engine and the
SQLite database:

  get_pending_images(conn, limit)   → list[dict]  images awaiting OCR
  get_failed_images(conn, limit)    → list[dict]  images where OCR failed
  save_ocr_result(conn, ...)        → None        UPSERT OCR result
  save_ocr_failed(conn, ...)        → None        mark image as failed

Design notes
────────────
* All queries use the ``dict_row_factory`` set by ``get_connection()`` so
  every returned row is a plain dict (easy serialisation + named access).
* ``save_ocr_result`` uses an INSERT OR REPLACE (UPSERT) so the caller may
  safely re-process an image without first deleting the old result.
* No connection lifecycle management here — the caller owns the connection.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Read helpers
# ─────────────────────────────────────────────────────────────────────────────


def get_pending_images(
    conn: sqlite3.Connection,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return images whose status is ``'pending'`` and have no OCR result yet.

    A ``LIMIT`` clause is applied only when *limit* is a positive integer,
    allowing callers to smoke-test with a small batch before running the full
    library.

    Args:
        conn:  Open SQLite connection with ``dict_row_factory`` configured.
        limit: Maximum number of rows to return.  ``None`` means no limit.

    Returns:
        A list of dicts with at least the keys:
        ``id``, ``filename``, ``original_path``, ``status``.
    """
    sql = """
        SELECT i.id, i.filename, i.original_path, i.status
        FROM   images AS i
        LEFT JOIN ocr_results AS ocr ON ocr.image_id = i.id
        WHERE  i.status = 'pending'
          AND  ocr.id IS NULL
        ORDER  BY i.id ASC
    """
    if limit is not None and limit > 0:
        sql += f" LIMIT {int(limit)}"

    return conn.execute(sql).fetchall()


def get_failed_images(
    conn: sqlite3.Connection,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return images where OCR previously failed (status ``'ocr_failed'``).

    Useful for ``--retry-failed`` mode: re-queue images that errored out in a
    prior run (e.g. because PaddleOCR was not installed at the time).

    Args:
        conn:  Open SQLite connection with ``dict_row_factory`` configured.
        limit: Maximum number of rows to return.  ``None`` means no limit.

    Returns:
        A list of dicts with at least the keys:
        ``id``, ``filename``, ``original_path``, ``status``.
    """
    sql = """
        SELECT id, filename, original_path, status
        FROM   images
        WHERE  status = 'ocr_failed'
        ORDER  BY id ASC
    """
    if limit is not None and limit > 0:
        sql += f" LIMIT {int(limit)}"

    return conn.execute(sql).fetchall()


# ─────────────────────────────────────────────────────────────────────────────
# Write helpers
# ─────────────────────────────────────────────────────────────────────────────


def save_ocr_result(
    conn: sqlite3.Connection,
    image_id: int,
    text: str,
    language: str,
    confidence: float,
    engine: str,
    word_count: int,
) -> None:
    """UPSERT an OCR result and update the parent image status.

    Uses ``INSERT OR REPLACE`` so the function is idempotent — calling it
    twice for the same *image_id* overwrites the previous row rather than
    raising an IntegrityError.

    Two statements are executed:
      1. UPSERT into ``ocr_results`` with the extracted text and metadata.
      2. UPDATE ``images.status`` to ``'ocr_done'`` for the same image.

    Both statements are run inside the caller's current transaction; the
    caller is responsible for committing (or checkpointing).

    Args:
        conn:        Open SQLite connection.
        image_id:    Primary key of the ``images`` row.
        text:        Full extracted text (may be empty string).
        language:    Language code used / detected (e.g. ``"en"``).
        confidence:  Mean word confidence in [0.0, 100.0].
        engine:      Engine identifier — ``"paddleocr"`` or ``"tesseract"``.
        word_count:  Number of words in *text*.
    """
    now: str = datetime.now(tz=timezone.utc).isoformat()

    # UPSERT into ocr_results — the UNIQUE constraint on image_id causes a
    # REPLACE when a conflicting row already exists.
    conn.execute(
        """
        INSERT OR REPLACE INTO ocr_results
            (image_id, extracted_text, language, confidence, engine, word_count, processed_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?)
        """,
        (image_id, text, language, confidence, engine, word_count, now),
    )

    # Advance the pipeline status so downstream stages know OCR is done.
    conn.execute(
        "UPDATE images SET status = 'ocr_done' WHERE id = ?",
        (image_id,),
    )


def save_ocr_failed(
    conn: sqlite3.Connection,
    image_id: int,
    error_msg: str,
) -> None:
    """Mark an image as OCR-failed in the ``images`` table.

    The error message is intentionally stored only in the application log
    (the caller should log it); the ``images`` table only records the status
    transition so the pipeline can resume selectively.

    Args:
        conn:      Open SQLite connection.
        image_id:  Primary key of the ``images`` row.
        error_msg: Human-readable error description (used only for logging
                   by the caller; not persisted to DB).
    """
    conn.execute(
        "UPDATE images SET status = 'ocr_failed' WHERE id = ?",
        (image_id,),
    )
