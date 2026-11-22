"""backend/api/routes/categories.py — category browse endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.api.models import CategoryInfo, SubcategoryInfo, ImageBase
from backend.config import CATEGORIES_FILE, DATABASE
from backend.db.database import get_connection
from backend.db.categories import (
    get_category_counts,
    get_subcategory_counts,
    get_images_by_category,
    get_full_category_tree,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryInfo])
def list_categories():
    """Return all categories with subcategory breakdowns and counts."""
    conn = get_connection(DATABASE)
    cat_counts = {r["category"]: r["count"] for r in get_category_counts(conn)}
    tree = get_full_category_tree(conn)
    conn.close()

    result = []
    for cat, subs in tree.items():
        sub_list = [SubcategoryInfo(name=k, count=v) for k, v in subs.items()]
        result.append(CategoryInfo(
            name=cat,
            subcategories=sub_list,
            count=cat_counts.get(cat, 0),
        ))
    return result


@router.get("/tree")
def category_tree():
    """Return the full category tree with counts as nested JSON."""
    conn = get_connection(DATABASE)
    tree = get_full_category_tree(conn)
    conn.close()

    # Enrich with predefined structure from categories.json
    if CATEGORIES_FILE.exists():
        with open(CATEGORIES_FILE, encoding="utf-8") as f:
            predefined = json.load(f)
        # Add categories that exist in predefined but have no images yet
        for cat, subs in predefined.items():
            if cat not in tree:
                tree[cat] = {sub: 0 for sub in subs}

    return tree


@router.get("/{category_name}/images", response_model=list[ImageBase])
def images_by_category(
    category_name: str,
    subcategory: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return images in a specific category, optionally filtered by subcategory."""
    conn = get_connection(DATABASE)
    rows = get_images_by_category(
        conn,
        category=category_name,
        subcategory=subcategory,
        limit=limit,
        offset=offset,
    )
    conn.close()
    return [ImageBase(**r) for r in rows]
