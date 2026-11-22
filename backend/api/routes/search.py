"""backend/api/routes/search.py — keyword, semantic, hybrid search endpoints."""
from __future__ import annotations

import time

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.api.models import SearchResponse, SearchResult
from backend.config import DATABASE
from backend.db.database import get_connection
from backend.db.search import keyword_search, hybrid_search
from backend.pipeline.embeddings import semantic_search

router = APIRouter(prefix="/search", tags=["search"])


def _rows_to_results(rows: list[dict], mode: str) -> list[SearchResult]:
    results = []
    for r in rows:
        results.append(SearchResult(
            image_id=r.get("id", r.get("image_id", 0)),
            filename=r.get("filename", ""),
            original_path=r.get("original_path", ""),
            width=r.get("width"),
            height=r.get("height"),
            captured_at=r.get("captured_at"),
            category=r.get("category"),
            subcategory=r.get("subcategory"),
            content_type=r.get("content_type"),
            tags=r.get("tags") or [],
            snippet=r.get("snippet", ""),
            score=float(r.get("score", 0.0)),
            search_mode=mode,
        ))
    return results


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="Search query"),
    mode: str = Query("keyword", pattern="^(keyword|semantic|hybrid)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Search the screenshot library.

    - **keyword**: SQLite FTS5 full-text search (fast, exact/prefix match)
    - **semantic**: CLIP embedding similarity (finds by meaning)
    - **hybrid**: merges both and re-ranks by combined score
    """
    t0 = time.monotonic()
    conn = get_connection(DATABASE)

    try:
        if mode == "keyword":
            rows = keyword_search(conn, q, limit=limit, offset=offset)
            results = _rows_to_results(rows, "keyword")

        elif mode == "semantic":
            sem = semantic_search(q, n_results=limit)
            if not sem:
                results = []
            else:
                # Fetch image rows for the returned IDs
                ids = [str(r["image_id"]) for r in sem]
                dist_map = {r["image_id"]: r["distance"] for r in sem}
                placeholders = ",".join("?" * len(ids))
                rows = conn.execute(
                    f"""
                    SELECT i.id, i.filename, i.original_path, i.width, i.height,
                           i.captured_at, c.category, c.subcategory,
                           c.content_type, c.tags
                    FROM images i
                    LEFT JOIN categories c ON i.id = c.image_id
                    WHERE i.id IN ({placeholders})
                    """,
                    [int(x) for x in ids],
                ).fetchall()
                from backend.db.search import _row_to_image_dict
                result_map = {r["id"]: _row_to_image_dict(r) for r in rows}
                ordered = []
                for s in sem:
                    img_id = s["image_id"]
                    if img_id in result_map:
                        d = result_map[img_id]
                        d["score"] = round(1.0 - s["distance"], 4)
                        ordered.append(d)
                results = _rows_to_results(ordered, "semantic")

        else:  # hybrid
            sem = semantic_search(q, n_results=limit * 2)
            rows = hybrid_search(conn, q, sem, limit=limit, offset=offset)
            results = _rows_to_results(rows, "hybrid")

    finally:
        conn.close()

    elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
    return SearchResponse(
        query=q,
        mode=mode,
        total=len(results),
        results=results,
        time_ms=elapsed_ms,
    )
