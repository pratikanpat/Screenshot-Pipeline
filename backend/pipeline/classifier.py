"""
backend/pipeline/classifier.py
───────────────────────────────
Two-stage screenshot classifier.

Stage 1 — Rule engine (fast, deterministic):
  Uses keyword matching via ``backend.pipeline.rules.classify_by_rules``.
  If a confident rule fires, we skip the more expensive CLIP call.

Stage 2 — CLIP zero-shot (semantic, no training data needed):
  Uses the sentence-transformers CLIP model to compare the image against a
  fixed list of natural-language category descriptions.

Both stages also call ``extract_tags`` to build a tag list from the OCR text.

If sentence-transformers / torch is not installed the module falls back to
rule-based-only classification without raising.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from PIL import Image
from tqdm import tqdm

from backend.config import (
    CATEGORIES_FILE,
    CHECKPOINT_INTERVAL,
    CLIP_MODEL,
    LOGS_DIR,
)
from backend.db.categories import save_category, build_fts_index
from backend.pipeline.logger import setup_logger
from backend.pipeline.rules import classify_by_rules, extract_tags

logger = setup_logger("classifier", LOGS_DIR / "classifier.log")

# ─────────────────────────────────────────────────────────────────────────────
# Optional CLIP import
# ─────────────────────────────────────────────────────────────────────────────

try:
    from sentence_transformers import SentenceTransformer  # type: ignore[import]
    CLIP_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment,misc]
    CLIP_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# CLIP label sets for zero-shot classification
# ─────────────────────────────────────────────────────────────────────────────

CLIP_CATEGORY_LABELS: list[str] = [
    "receipt or invoice or payment",
    "bank statement or financial document",
    "upi or mobile payment transaction",
    "computer code or programming",
    "AI or machine learning content",
    "open source or GitHub activity",
    "technology tutorial or how-to guide",
    "LinkedIn post or professional network",
    "Twitter or X post or tweet",
    "Instagram post or story or reel",
    "YouTube video or channel",
    "motivational quote or inspiration",
    "online course or lesson",
    "article or blog post or newsletter",
    "personal notes or summary",
    "book highlight or reading",
    "WhatsApp or Telegram chat message",
    "reminder or to-do or alarm",
    "calendar event or schedule",
    "map or navigation directions",
    "movie or show or streaming",
    "music or playlist or album",
    "online shopping or product or order",
    "other or uncategorized",
]

# Maps CLIP label index → (category, subcategory, content_type)
CLIP_LABEL_MAPPING: list[tuple[str, str, str]] = [
    ("Finance", "Receipts & Invoices", "receipt"),
    ("Finance", "Bank Statements", "document"),
    ("Finance", "UPI Transactions", "transaction"),
    ("Technology", "Code & Development", "code"),
    ("Technology", "AI & Machine Learning", "article"),
    ("Technology", "Open Source", "post"),
    ("Technology", "Tutorials", "article"),
    ("Social & Content", "LinkedIn", "post"),
    ("Social & Content", "Twitter/X", "post"),
    ("Social & Content", "Instagram", "post"),
    ("Social & Content", "YouTube", "post"),
    ("Social & Content", "Quotes & Inspiration", "quote"),
    ("Learning", "Courses", "article"),
    ("Learning", "Articles & Blogs", "article"),
    ("Learning", "Notes", "note"),
    ("Learning", "Books & Reading", "document"),
    ("Personal", "Chats & Messages", "chat"),
    ("Personal", "Reminders", "reminder"),
    ("Personal", "Calendar & Events", "calendar"),
    ("Maps & Places", "Navigation", "map"),
    ("Media & Entertainment", "Movies & Shows", "media"),
    ("Media & Entertainment", "Music", "media"),
    ("Finance", "Shopping", "receipt"),
    ("Other", "Uncategorized", "other"),
]

# ─────────────────────────────────────────────────────────────────────────────
# CLIP model loader (singleton)
# ─────────────────────────────────────────────────────────────────────────────

_clip_model: Any = None


def load_clip_model() -> Any:
    """Load (and cache) the CLIP model. Returns None if unavailable."""
    global _clip_model
    if _clip_model is not None:
        return _clip_model
    if not CLIP_AVAILABLE:
        logger.warning("sentence-transformers not installed — CLIP unavailable.")
        return None
    try:
        logger.info("Loading CLIP model: %s", CLIP_MODEL)
        _clip_model = SentenceTransformer(CLIP_MODEL)
        logger.info("CLIP model loaded.")
        return _clip_model
    except Exception as exc:
        logger.warning("Failed to load CLIP model: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Zero-shot classification via CLIP
# ─────────────────────────────────────────────────────────────────────────────

def _clip_classify(image: Image.Image, model: Any) -> tuple[str, str, str, float]:
    """
    Use CLIP to pick the best-matching category for *image*.

    Returns (category, subcategory, content_type, confidence_0_to_1).
    """
    import torch  # noqa: PLC0415

    # Encode image
    img_emb = model.encode(image, convert_to_tensor=True)

    # Encode all label strings
    label_embs = model.encode(CLIP_CATEGORY_LABELS, convert_to_tensor=True)

    # Cosine similarity
    sims = torch.nn.functional.cosine_similarity(
        img_emb.unsqueeze(0), label_embs, dim=1
    )
    best_idx = int(sims.argmax())
    best_score = float(sims[best_idx])

    cat, sub, ctype = CLIP_LABEL_MAPPING[best_idx]
    return cat, sub, ctype, best_score


# ─────────────────────────────────────────────────────────────────────────────
# Public: classify one image
# ─────────────────────────────────────────────────────────────────────────────

def classify_image(
    image: Image.Image,
    ocr_text: str,
    clip_model: Any = None,
) -> dict:
    """
    Classify *image* and return a result dict with keys:
      category, subcategory, content_type, tags (list), confidence, method
    """
    tags = extract_tags(ocr_text)

    # Stage 1: rule engine
    rule_match = classify_by_rules(ocr_text)
    if rule_match:
        return {
            "category": rule_match["category"],
            "subcategory": rule_match["subcategory"],
            "content_type": rule_match["content_type"],
            "tags": tags,
            "confidence": 0.95,
            "method": "rule_based",
        }

    # Stage 2: CLIP zero-shot
    if clip_model is not None:
        try:
            cat, sub, ctype, score = _clip_classify(image, clip_model)
            return {
                "category": cat,
                "subcategory": sub,
                "content_type": ctype,
                "tags": tags,
                "confidence": round(score, 4),
                "method": "clip_zeroshot",
            }
        except Exception as exc:
            logger.warning("CLIP classification failed: %s", exc)

    # Fallback: unclassified
    return {
        "category": "Other",
        "subcategory": "Uncategorized",
        "content_type": "other",
        "tags": tags,
        "confidence": 0.0,
        "method": "fallback",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Process one image (DB-integrated)
# ─────────────────────────────────────────────────────────────────────────────

def process_image_classify(
    conn: sqlite3.Connection,
    image_id: int,
    image_path: Path,
    ocr_text: str,
    clip_model: Any = None,
) -> str:
    """Open image, classify, persist results. Returns 'success' or 'failed'."""
    try:
        with Image.open(image_path) as img:
            image = img.convert("RGB")

        result = classify_image(image, ocr_text, clip_model)

        save_category(
            conn=conn,
            image_id=image_id,
            category=result["category"],
            subcategory=result["subcategory"],
            content_type=result["content_type"],
            tags_list=result["tags"],
            confidence=result["confidence"],
            method=result["method"],
        )

        build_fts_index(
            conn=conn,
            image_id=image_id,
            text_content=ocr_text,
            tags_list=result["tags"],
        )

        return "success"

    except Exception as exc:
        logger.error("classify failed for image_id=%d: %s", image_id, exc)
        return "failed"


# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────

def run_classification(
    conn: sqlite3.Connection,
    limit: int | None = None,
    force: bool = False,
) -> dict:
    """
    Classify all images that have OCR results but no category yet.

    Returns stats dict: total, success, failed, elapsed_s.
    """
    start = time.monotonic()

    if force:
        query = """
            SELECT i.id, i.original_path, o.extracted_text
            FROM images i
            LEFT JOIN ocr_results o ON i.id = o.image_id
            WHERE o.extracted_text IS NOT NULL
        """
    else:
        query = """
            SELECT i.id, i.original_path, o.extracted_text
            FROM images i
            LEFT JOIN ocr_results o ON i.id = o.image_id
            LEFT JOIN categories c ON i.id = c.image_id
            WHERE o.extracted_text IS NOT NULL
              AND c.image_id IS NULL
        """

    if limit:
        query += f" LIMIT {int(limit)}"

    rows = conn.execute(query).fetchall()
    total = len(rows)

    if total == 0:
        return {"total": 0, "success": 0, "failed": 0, "elapsed_s": 0.0}

    clip_model = load_clip_model()

    success, failed = 0, 0
    pending_since_commit = 0

    with tqdm(rows, desc="Classify", unit="img", dynamic_ncols=True) as bar:
        for row in bar:
            image_id = row["id"]
            outcome = process_image_classify(
                conn=conn,
                image_id=image_id,
                image_path=Path(row["original_path"]),
                ocr_text=row["extracted_text"] or "",
                clip_model=clip_model,
            )
            if outcome == "success":
                success += 1
            else:
                failed += 1

            pending_since_commit += 1
            if pending_since_commit >= CHECKPOINT_INTERVAL:
                conn.commit()
                pending_since_commit = 0

    conn.commit()
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "elapsed_s": round(time.monotonic() - start, 2),
    }

