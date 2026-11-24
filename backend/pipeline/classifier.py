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
    # Finance
    "a PhonePe payment confirmation screen",
    "a Google Pay or GPay payment confirmation",
    "a Paytm transaction or wallet screen",
    "a MobiKwik or digital wallet payment",
    "a UPI payment or bank transfer transaction",
    "a receipt, invoice, or bill with itemized amounts",
    "a GST tax invoice or purchase receipt",
    "a bank account statement or passbook",
    "an e-commerce order confirmation from Flipkart Amazon Meesho",
    "a personal finance budget or expense tracker",
    # Social Media — Instagram
    "an Instagram direct message chat conversation",
    "an Instagram feed post with photo and caption",
    "an Instagram story or reel video",
    "an Instagram profile page with followers count",
    # Social Media — Other platforms
    "a Twitter or X post tweet or thread",
    "a LinkedIn professional post or job update",
    "a WhatsApp chat conversation or group message",
    "a Telegram chat or channel message",
    "a YouTube video page or channel",
    "a Reddit post or comment thread",
    "a Facebook post or news feed",
    "a Snapchat snap or story",
    "a motivational or inspirational quote",
    # Technology
    "a computer code editor or programming terminal",
    "an AI chatbot conversation like ChatGPT Gemini Claude",
    "a GitHub repository or pull request",
    "a technology tutorial or how-to article",
    # Learning
    "an online course lesson from Udemy Coursera",
    "a blog article or newsletter",
    "handwritten or digital study notes",
    "a book page or Kindle highlight",
    # People & Faces
    "a portrait photo of a single person's face",
    "a group photo of multiple people together",
    "a circular profile picture or avatar of a person",
    "a selfie photo taken by the person themselves",
    # Personal
    "a reminder alarm or to-do list",
    "a calendar event or meeting schedule",
    "a contact card with phone number",
    # Maps & Places
    "a navigation map with directions or route",
    "a food delivery app like Zomato or Swiggy",
    "a ride-hailing app like Uber or Ola",
    # Media & Entertainment
    "a streaming app like Netflix Disney Hotstar",
    "a music player or album with song playing",
    "a mobile game or gaming leaderboard",
    # Health
    "a health fitness tracker with steps or calories",
    "a medical prescription or doctor report",
    # Other
    "a screenshot of miscellaneous or unrecognized content",
]

# Maps CLIP label index → (category, subcategory, content_type)
CLIP_LABEL_MAPPING: list[tuple[str, str, str]] = [
    # Finance
    ("Finance", "Payment Apps", "transaction"),           # PhonePe
    ("Finance", "Payment Apps", "transaction"),           # GPay
    ("Finance", "Payment Apps", "transaction"),           # Paytm
    ("Finance", "Payment Apps", "transaction"),           # MobiKwik
    ("Finance", "UPI Transactions", "transaction"),       # UPI
    ("Finance", "Receipts & Invoices", "receipt"),        # receipt/invoice
    ("Finance", "Receipts & Invoices", "receipt"),        # GST invoice
    ("Finance", "Bank Statements", "document"),           # bank statement
    ("Finance", "Shopping", "receipt"),                   # e-commerce order
    ("Finance", "Budgets", "document"),                   # budget
    # Instagram
    ("Social & Content", "Instagram Chats", "chat"),      # IG DM
    ("Social & Content", "Instagram Posts", "post"),      # IG post
    ("Social & Content", "Instagram Stories & Reels", "post"),  # IG story/reel
    ("Social & Content", "Instagram", "post"),            # IG profile
    # Other social
    ("Social & Content", "Twitter/X Posts", "post"),      # Twitter
    ("Social & Content", "LinkedIn Posts", "post"),       # LinkedIn
    ("Personal", "WhatsApp Chats", "chat"),               # WhatsApp
    ("Personal", "Telegram Chats", "chat"),               # Telegram
    ("Social & Content", "YouTube", "post"),              # YouTube
    ("Social & Content", "Reddit", "post"),               # Reddit
    ("Social & Content", "Facebook", "post"),             # Facebook
    ("Social & Content", "Snapchat", "post"),             # Snapchat
    ("Social & Content", "Quotes & Inspiration", "quote"), # quote
    # Technology
    ("Technology", "Code & Development", "code"),         # code
    ("Technology", "AI & Machine Learning", "article"),   # AI chatbot
    ("Technology", "Open Source", "post"),                # GitHub
    ("Technology", "Tutorials", "article"),               # tutorial
    # Learning
    ("Learning", "Courses", "article"),                   # online course
    ("Learning", "Articles & Blogs", "article"),          # blog
    ("Learning", "Notes", "note"),                        # notes
    ("Learning", "Books & Reading", "document"),          # book
    # People & Faces
    ("People & Faces", "Portraits", "photo"),             # portrait
    ("People & Faces", "Group Photos", "photo"),          # group photo
    ("People & Faces", "Profile Pictures", "photo"),      # circular profile pic
    ("People & Faces", "Portraits", "photo"),             # selfie
    # Personal
    ("Personal", "Reminders", "reminder"),                # reminder
    ("Personal", "Calendar & Events", "calendar"),        # calendar
    ("Personal", "Contacts", "contact"),                  # contact
    # Maps
    ("Maps & Places", "Navigation", "map"),               # navigation
    ("Maps & Places", "Food & Restaurants", "place"),     # food delivery
    ("Maps & Places", "Navigation", "map"),               # ride-hailing
    # Media
    ("Media & Entertainment", "Movies & Shows", "media"), # streaming
    ("Media & Entertainment", "Music", "media"),           # music
    ("Media & Entertainment", "Gaming", "media"),          # gaming
    # Health
    ("Health & Fitness", "Activity Tracking", "health"),  # fitness
    ("Health & Fitness", "Medical", "document"),           # medical
    # Other
    ("Other", "Uncategorized", "other"),                   # misc
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

