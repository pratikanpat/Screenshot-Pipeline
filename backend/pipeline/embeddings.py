"""
backend/pipeline/embeddings.py
───────────────────────────────
Generate CLIP image embeddings and store them in ChromaDB.

Embeddings power semantic search: encode a text query with the same CLIP model
and retrieve the nearest-neighbour images by cosine distance.

ChromaDB is optional — the module imports it lazily and degrades gracefully if
it is not installed.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from tqdm import tqdm

from backend.config import (
    CHECKPOINT_INTERVAL,
    CHROMA_DIR,
    CLIP_MODEL,
    LOGS_DIR,
)
from backend.pipeline.logger import setup_logger

logger = setup_logger("embeddings", LOGS_DIR / "embeddings.log")

# ─────────────────────────────────────────────────────────────────────────────
# Optional imports
# ─────────────────────────────────────────────────────────────────────────────

try:
    import chromadb  # type: ignore[import]
    CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore[assignment]
    CHROMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore[import]
    CLIP_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment,misc]
    CLIP_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB collection (singleton)
# ─────────────────────────────────────────────────────────────────────────────

_chroma_collection: Any = None


def get_chroma_collection() -> Any:
    """Return (and cache) the ChromaDB 'screenshots' collection."""
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    if not CHROMA_AVAILABLE:
        logger.warning("chromadb not installed — semantic search unavailable.")
        return None

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _chroma_collection = client.get_or_create_collection(
        name="screenshots",
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB collection ready (%d vectors).", _chroma_collection.count())
    return _chroma_collection


# ─────────────────────────────────────────────────────────────────────────────
# CLIP model (re-use from classifier if already loaded)
# ─────────────────────────────────────────────────────────────────────────────

_clip_model: Any = None


def _get_clip_model() -> Any:
    global _clip_model
    if _clip_model is not None:
        return _clip_model
    if not CLIP_AVAILABLE:
        return None
    try:
        _clip_model = SentenceTransformer(CLIP_MODEL)
        logger.info("CLIP model loaded for embeddings: %s", CLIP_MODEL)
        return _clip_model
    except Exception as exc:
        logger.warning("Could not load CLIP model: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def generate_embedding(image: Image.Image, clip_model: Any) -> list[float]:
    """Encode *image* using CLIP and return a plain Python list of floats."""
    emb = clip_model.encode(image)
    return emb.tolist()


def upsert_embedding(
    collection: Any,
    image_id: int,
    embedding: list[float],
    metadata: dict,
) -> None:
    """Add or replace an embedding in ChromaDB."""
    collection.upsert(
        ids=[str(image_id)],
        embeddings=[embedding],
        metadatas=[metadata],
    )


def semantic_search(
    query_text: str,
    n_results: int = 20,
) -> list[dict]:
    """
    Encode *query_text* with CLIP and return the nearest screenshot IDs.

    Returns list of dicts: {image_id, distance, metadata}.
    """
    collection = get_chroma_collection()
    model = _get_clip_model()

    if collection is None or model is None:
        return []

    try:
        query_emb = model.encode(query_text).tolist()
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=min(n_results, max(1, collection.count())),
        )

        output: list[dict] = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for doc_id, dist, meta in zip(ids, distances, metas):
            output.append({
                "image_id": int(doc_id),
                "distance": float(dist),
                "metadata": meta or {},
            })
        return output

    except Exception as exc:
        logger.error("semantic_search failed: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────

def run_embeddings(
    conn: sqlite3.Connection,
    limit: int | None = None,
    force: bool = False,
) -> dict:
    """
    Generate CLIP embeddings for every classified image that doesn't have one.

    Returns stats dict: total, success, failed, elapsed_s.
    """
    start = time.monotonic()

    collection = get_chroma_collection()
    model = _get_clip_model()

    if collection is None or model is None:
        logger.warning(
            "Embeddings skipped — ChromaDB or CLIP model unavailable."
        )
        return {"total": 0, "success": 0, "failed": 0, "elapsed_s": 0.0,
                "skipped": True}

    if force:
        query = "SELECT id, original_path, filename FROM images WHERE status IN ('classified','ocr_done','processed')"
    else:
        query = """
            SELECT i.id, i.original_path, i.filename
            FROM images i
            LEFT JOIN embeddings e ON i.id = e.image_id
            WHERE i.status IN ('classified', 'ocr_done', 'processed')
              AND e.image_id IS NULL
        """
    if limit:
        query += f" LIMIT {int(limit)}"

    rows = conn.execute(query).fetchall()
    total = len(rows)

    if total == 0:
        return {"total": 0, "success": 0, "failed": 0, "elapsed_s": 0.0}

    success, failed = 0, 0
    pending = 0

    with tqdm(rows, desc="Embed", unit="img", dynamic_ncols=True) as bar:
        for row in bar:
            image_id = row["id"]
            try:
                with Image.open(row["original_path"]) as img:
                    image = img.convert("RGB")

                emb = generate_embedding(image, model)
                upsert_embedding(
                    collection=collection,
                    image_id=image_id,
                    embedding=emb,
                    metadata={"filename": row["filename"]},
                )

                now = datetime.now().isoformat(sep=" ")
                conn.execute(
                    """
                    INSERT INTO embeddings (image_id, model, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(image_id) DO UPDATE SET
                        model = excluded.model,
                        created_at = excluded.created_at
                    """,
                    (image_id, CLIP_MODEL, now),
                )

                success += 1

            except Exception as exc:
                logger.error("Embed failed image_id=%d: %s", image_id, exc)
                failed += 1

            pending += 1
            if pending >= CHECKPOINT_INTERVAL:
                conn.commit()
                pending = 0

    conn.commit()
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "elapsed_s": round(time.monotonic() - start, 2),
    }
