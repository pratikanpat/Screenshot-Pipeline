"""
backend/db/categories.py
─────────────────────────
Database operations for the categories and FTS5 index tables.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────────────────────────────────────

def save_category(
    conn: sqlite3.Connection,
    image_id: int,
    category: str,
    subcategory: str,
    content_type: str,
    tags_list: list[str],
    confidence: float,
    method: str,
) -> None:
    """Upsert a category record and update the parent image status."""
    tags_json = json.dumps(tags_list, ensure_ascii=False)
    now = datetime.now().isoformat(sep=" ")

    conn.execute(
        """
        INSERT INTO categories
            (image_id, category, subcategory, content_type, tags, confidence, method, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(image_id) DO UPDATE SET
            category     = excluded.category,
            subcategory  = excluded.subcategory,
            content_type = excluded.content_type,
            tags         = excluded.tags,
            confidence   = excluded.confidence,
            method       = excluded.method,
            created_at   = excluded.created_at
        """,
        (image_id, category, subcategory, content_type,
         tags_json, confidence, method, now),
    )

    conn.execute(
        "UPDATE images SET status = 'classified' WHERE id = ?",
        (image_id,),
    )


def build_fts_index(
    conn: sqlite3.Connection,
    image_id: int,
    text_content: str,
    tags_list: list[str],
) -> None:
    """
    Insert or replace the FTS5 record for this image.

    FTS5 does not support ON CONFLICT, so we delete then insert.
    """
    tags_str = " ".join(tags_list)

    conn.execute(
        "DELETE FROM fts_index WHERE image_id = ?",
        (image_id,),
    )
    conn.execute(
        "INSERT INTO fts_index (image_id, text_content, tags) VALUES (?, ?, ?)",
        (image_id, text_content or "", tags_str),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Read operations
# ─────────────────────────────────────────────────────────────────────────────

def get_category_counts(conn: sqlite3.Connection) -> list[dict]:
    """Return [{category, count}] ordered by count desc."""
    rows = conn.execute(
        """
        SELECT category, COUNT(*) AS count
        FROM categories
        GROUP BY category
        ORDER BY count DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_subcategory_counts(conn: sqlite3.Connection, category: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT subcategory, COUNT(*) AS count
        FROM categories
        WHERE category = ?
        GROUP BY subcategory
        ORDER BY count DESC
        """,
        (category,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_images_by_category(
    conn: sqlite3.Connection,
    category: str,
    subcategory: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return paginated image rows for a given category (and optional subcategory)."""
    base = """
        SELECT i.id, i.filename, i.original_path, i.width, i.height,
               i.captured_at, i.status,
               c.category, c.subcategory, c.content_type, c.tags, c.confidence
        FROM images i
        JOIN categories c ON i.id = c.image_id
        WHERE c.category = ?
    """
    params: list = [category]

    if subcategory:
        base += " AND c.subcategory = ?"
        params.append(subcategory)

    base += " ORDER BY i.captured_at DESC NULLS LAST LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = conn.execute(base, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d["tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
        result.append(d)
    return result


def get_full_category_tree(conn: sqlite3.Connection) -> dict:
    """
    Return a nested dict: {category: {subcategory: count}}.
    """
    rows = conn.execute(
        """
        SELECT category, subcategory, COUNT(*) AS count
        FROM categories
        GROUP BY category, subcategory
        ORDER BY category, count DESC
        """
    ).fetchall()

    tree: dict[str, dict[str, int]] = {}
    for row in rows:
        cat = row["category"]
        sub = row["subcategory"]
        cnt = row["count"]
        tree.setdefault(cat, {})[sub] = cnt
    return tree
