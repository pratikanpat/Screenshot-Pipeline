"""
backend/db/search.py
─────────────────────
Database-layer search functions.

keyword_search   — SQLite FTS5 full-text search
semantic_search  — delegates to embeddings.semantic_search (ChromaDB + CLIP)
hybrid_search    — merges and re-ranks both result sets
get_image_detail — single-image detail join
get_images_paginated — paginated image list
"""

from __future__ import annotations

import json
import re
import sqlite3


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_fts_query(raw: str) -> str:
    """
    Escape characters that have special meaning in SQLite FTS5 queries.
    Preserves quoted phrases ("multi word") and prefix searches (word*).
    """
    # Allow alphanumeric, spaces, quotes, asterisk
    cleaned = re.sub(r'[^\w\s"*]', " ", raw, flags=re.UNICODE)
    return cleaned.strip() or '""'


def _row_to_image_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Keyword search (FTS5)
# ─────────────────────────────────────────────────────────────────────────────

def keyword_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Full-text search using SQLite FTS5.

    Returns list of image dicts with an additional 'snippet' and 'score' key.
    score is -rank (higher = better match).
    """
    safe_q = _safe_fts_query(query)

    rows = conn.execute(
        """
        SELECT
            i.id,
            i.filename,
            i.original_path,
            i.width,
            i.height,
            i.captured_at,
            i.status,
            c.category,
            c.subcategory,
            c.content_type,
            c.tags,
            c.confidence   AS cat_confidence,
            snippet(fts_index, 1, '<b>', '</b>', '…', 20) AS snippet,
            (-fts_index.rank)                             AS score
        FROM fts_index
        JOIN images     i ON i.id = fts_index.image_id
        LEFT JOIN categories c ON c.image_id = i.id
        WHERE fts_index MATCH ?
        ORDER BY fts_index.rank
        LIMIT ? OFFSET ?
        """,
        (safe_q, limit, offset),
    ).fetchall()

    return [_row_to_image_dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid search (keyword + semantic merged)
# ─────────────────────────────────────────────────────────────────────────────

def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    semantic_results: list[dict],  # from embeddings.semantic_search
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Merge keyword (FTS5) and semantic (CLIP) results.

    Scoring: normalised_fts_score * 0.5 + (1 - cosine_distance) * 0.5
    """
    # Keyword pass — fetch more than limit for re-ranking
    kw_rows = keyword_search(conn, query, limit=limit * 3, offset=0)

    # Build lookup tables
    kw_by_id: dict[int, dict] = {r["id"]: r for r in kw_rows}
    sem_by_id: dict[int, float] = {
        r["image_id"]: 1.0 - r["distance"]  # cosine similarity
        for r in semantic_results
    }

    # Gather all unique IDs
    all_ids = set(kw_by_id.keys()) | set(sem_by_id.keys())

    # Normalise FTS scores
    max_kw = max((kw_by_id[i]["score"] for i in kw_by_id), default=1.0) or 1.0

    scored: list[tuple[float, int]] = []
    for img_id in all_ids:
        kw_score = kw_by_id[img_id]["score"] / max_kw if img_id in kw_by_id else 0.0
        sem_score = sem_by_id.get(img_id, 0.0)
        combined = kw_score * 0.5 + sem_score * 0.5
        scored.append((combined, img_id))

    scored.sort(key=lambda x: x[0], reverse=True)
    page_ids = [img_id for _, img_id in scored[offset: offset + limit]]

    if not page_ids:
        return []

    # Fetch full rows for page IDs
    placeholders = ",".join("?" * len(page_ids))
    rows = conn.execute(
        f"""
        SELECT i.id, i.filename, i.original_path, i.width, i.height,
               i.captured_at, i.status,
               c.category, c.subcategory, c.content_type, c.tags
        FROM images i
        LEFT JOIN categories c ON c.image_id = i.id
        WHERE i.id IN ({placeholders})
        """,
        page_ids,
    ).fetchall()

    # Attach scores, preserve order
    score_map = {img_id: sc for sc, img_id in scored}
    result_map = {r["id"]: _row_to_image_dict(r) for r in rows}

    ordered = []
    for img_id in page_ids:
        if img_id in result_map:
            d = result_map[img_id]
            d["score"] = round(score_map[img_id], 4)
            d["snippet"] = kw_by_id[img_id].get("snippet", "") if img_id in kw_by_id else ""
            ordered.append(d)

    return ordered


# ─────────────────────────────────────────────────────────────────────────────
# Single image detail
# ─────────────────────────────────────────────────────────────────────────────

def get_image_detail(conn: sqlite3.Connection, image_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT i.id, i.filename, i.original_path, i.width, i.height,
               i.captured_at, i.modified_at, i.file_size, i.sha256, i.status,
               o.extracted_text, o.language, o.confidence AS ocr_confidence,
               o.engine, o.word_count,
               c.category, c.subcategory, c.content_type, c.tags,
               c.confidence AS cat_confidence, c.method
        FROM images i
        LEFT JOIN ocr_results  o ON i.id = o.image_id
        LEFT JOIN categories   c ON i.id = c.image_id
        WHERE i.id = ?
        """,
        (image_id,),
    ).fetchone()

    if row is None:
        return None

    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Paginated image list
# ─────────────────────────────────────────────────────────────────────────────

def get_images_paginated(
    conn: sqlite3.Connection,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    base = """
        SELECT i.id, i.filename, i.original_path, i.width, i.height,
               i.captured_at, i.status,
               c.category, c.subcategory, c.tags
        FROM images i
        LEFT JOIN categories c ON i.id = c.image_id
    """
    params: list = []
    if status:
        base += " WHERE i.status = ?"
        params.append(status)

    base += " ORDER BY i.captured_at DESC NULLS LAST LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = conn.execute(base, params).fetchall()
    return [_row_to_image_dict(r) for r in rows]


def get_library_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    processed = conn.execute(
        "SELECT COUNT(*) FROM images WHERE status = 'classified'"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM images WHERE status = 'pending'"
    ).fetchone()[0]
    failed = conn.execute(
        "SELECT COUNT(*) FROM images WHERE status LIKE '%failed%'"
    ).fetchone()[0]

    return {
        "total": total,
        "processed": processed,
        "pending": pending,
        "failed": failed,
    }
