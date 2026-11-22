"""backend/api/routes/images.py — image endpoints."""
from __future__ import annotations

import io
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image

from backend.api.models import ImageBase, ImageDetail
from backend.config import DATABASE, THUMBNAIL_SIZE
from backend.db.database import get_connection
from backend.db.search import get_image_detail, get_images_paginated

router = APIRouter(prefix="/images", tags=["images"])


@router.get("", response_model=list[ImageBase])
def list_images(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
):
    """Return a paginated list of images."""
    conn = get_connection(DATABASE)
    rows = get_images_paginated(conn, status=status, limit=limit, offset=offset)
    conn.close()
    return [ImageBase(**r) for r in rows]


@router.get("/{image_id}", response_model=ImageDetail)
def get_image(image_id: int):
    """Return full detail for one image."""
    conn = get_connection(DATABASE)
    row = get_image_detail(conn, image_id)
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    return ImageDetail(**row)


@router.get("/{image_id}/file")
def serve_original(image_id: int):
    """Stream the original screenshot file."""
    conn = get_connection(DATABASE)
    row = get_image_detail(conn, image_id)
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    path = Path(row["original_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk.")
    return FileResponse(str(path), media_type="image/png")


@router.get("/{image_id}/thumbnail")
def serve_thumbnail(image_id: int):
    """
    Return a JPEG thumbnail (letterboxed to THUMBNAIL_SIZE).
    Generated on-the-fly; no caching layer needed for a local tool.
    """
    conn = get_connection(DATABASE)
    row = get_image_detail(conn, image_id)
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Image not found.")

    path = Path(row["original_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk.")

    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)

            # Letterbox onto a white canvas
            canvas = Image.new("RGB", THUMBNAIL_SIZE, (245, 245, 245))
            x = (THUMBNAIL_SIZE[0] - img.width) // 2
            y = (THUMBNAIL_SIZE[1] - img.height) // 2
            canvas.paste(img, (x, y))

            buf = io.BytesIO()
            canvas.save(buf, format="JPEG", quality=85)
            buf.seek(0)

        return StreamingResponse(buf, media_type="image/jpeg")

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Thumbnail error: {exc}")
