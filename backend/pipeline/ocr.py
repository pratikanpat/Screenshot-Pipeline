"""
backend/pipeline/ocr.py
───────────────────────
OCR engine for the Screenshot Knowledge Base.

Strategy
────────
1. Preprocess the image with ``preprocessor.enhance_for_ocr`` (upscale,
   sharpen, invert dark-mode screenshots).
2. Try **PaddleOCR** (primary): initialised once per batch run (expensive).
3. If PaddleOCR's confidence < OCR_CONFIDENCE_THRESHOLD **or** fewer than
   OCR_MIN_WORDS words were found, fall back to **pytesseract** and pick the
   better result.
4. Save the winning result (or failure) to the database via ``backend.db.ocr``.

Graceful degradation
────────────────────
* If PaddleOCR is not installed the import is caught at module load time and
  the engine silently drops to Tesseract-only mode.
* Tesseract's executable path is auto-detected on Windows.

Public API
──────────
  _run_paddleocr(image, paddle_instance) → dict
  _run_tesseract(image)                  → dict
  extract_text(image, paddle_instance)   → dict (best result)
  process_image_ocr(conn, image_id, image_path, paddle_instance) → str
  run_ocr(conn, limit, force, retry_failed) → dict (stats)
"""

from __future__ import annotations

import logging
import platform
import sqlite3
import time
from pathlib import Path
from typing import Any

from PIL import Image
from tqdm import tqdm

from backend.config import (
    CHECKPOINT_INTERVAL,
    LOGS_DIR,
    OCR_CONFIDENCE_THRESHOLD,
    OCR_MIN_WORDS,
    PADDLE_LANG,
    TESSERACT_CONFIG,
)
from backend.db.ocr import (
    get_failed_images,
    get_pending_images,
    save_ocr_failed,
    save_ocr_result,
)
from backend.pipeline.logger import setup_logger
from backend.pipeline.preprocessor import enhance_for_ocr

# ─────────────────────────────────────────────────────────────────────────────
# Optional PaddleOCR import — falls back to Tesseract-only if not installed
# ─────────────────────────────────────────────────────────────────────────────

try:
    from paddleocr import PaddleOCR as _PaddleOCR  # type: ignore[import]

    PADDLE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PaddleOCR = None  # type: ignore[assignment,misc]
    PADDLE_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Tesseract executable auto-detection (Windows path not on PATH by default)
# ─────────────────────────────────────────────────────────────────────────────

try:
    import pytesseract  # type: ignore[import]

    _WIN_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if platform.system() == "Windows" and _WIN_TESSERACT.exists():
        pytesseract.pytesseract.tesseract_cmd = str(_WIN_TESSERACT)

    TESSERACT_AVAILABLE = True
except ImportError:  # pragma: no cover
    pytesseract = None  # type: ignore[assignment]
    TESSERACT_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Module logger
# ─────────────────────────────────────────────────────────────────────────────

logger = setup_logger("pipeline.ocr", LOGS_DIR / "ocr.log")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

#: Returned as the ``language`` field when no language detection is available.
_DEFAULT_LANG: str = "en"

#: Sentinel dict returned when an engine produces no output.
_EMPTY_RESULT: dict[str, Any] = {
    "text": "",
    "language": _DEFAULT_LANG,
    "confidence": 0.0,
    "word_count": 0,
    "engine": "none",
}


# ─────────────────────────────────────────────────────────────────────────────
# Engine runners
# ─────────────────────────────────────────────────────────────────────────────


def _run_paddleocr(
    image: Image.Image,
    paddle_instance: Any,
) -> dict[str, Any]:
    """Run PaddleOCR on *image* and return a normalised result dict.

    PaddleOCR returns a nested list::

        [                              # one entry per image in the batch
            [                          # list of detected text regions
                [bbox, (text, score)],
                ...
            ]
        ]

    This function flattens the structure, filters empty lines, and computes
    the per-word average confidence.

    Args:
        image:           PIL ``Image`` (RGB, already pre-processed).
        paddle_instance: Initialised ``PaddleOCR`` instance.

    Returns:
        dict with keys: ``text``, ``language``, ``confidence``,
        ``word_count``, ``engine``.
    """
    import numpy as np  # local import — avoids hard dependency at module level

    img_array = np.array(image)

    try:
        raw = paddle_instance.ocr(img_array, cls=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("PaddleOCR inference failed: %s", exc)
        return dict(_EMPTY_RESULT, engine="paddleocr")

    lines: list[str] = []
    confidences: list[float] = []

    # ``raw`` may be None or [[None]] for blank images.
    if raw is None:
        return dict(_EMPTY_RESULT, engine="paddleocr")

    for page in raw:
        if page is None:
            continue
        for region in page:
            if region is None:
                continue
            # region = [bbox, (text, score)]
            try:
                _bbox, (text, score) = region
            except (TypeError, ValueError):
                continue

            text = (text or "").strip()
            if not text:
                continue

            lines.append(text)
            confidences.append(float(score) * 100.0)  # PaddleOCR scores are 0–1

    full_text = " ".join(lines)
    word_count = len(full_text.split()) if full_text.strip() else 0
    avg_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

    return {
        "text": full_text,
        "language": PADDLE_LANG,
        "confidence": round(avg_confidence, 2),
        "word_count": word_count,
        "engine": "paddleocr",
    }


def _run_tesseract(image: Image.Image) -> dict[str, Any]:
    """Run pytesseract on *image* and return a normalised result dict.

    Uses ``image_to_data`` (TSV output) to retrieve per-word confidence
    scores so we can compute an accurate average — unlike ``image_to_string``
    which provides no confidence information.

    Args:
        image: PIL ``Image`` (RGB, already pre-processed).

    Returns:
        dict with keys: ``text``, ``language``, ``confidence``,
        ``word_count``, ``engine``.
    """
    if not TESSERACT_AVAILABLE:
        logger.warning("pytesseract not installed — cannot run Tesseract fallback.")
        return dict(_EMPTY_RESULT, engine="tesseract")

    try:
        # image_to_data returns a TSV string; output_type=pytesseract.Output.DICT
        # gives us Python dicts with 'text' and 'conf' lists.
        data = pytesseract.image_to_data(
            image,
            config=TESSERACT_CONFIG,
            output_type=pytesseract.Output.DICT,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tesseract inference failed: %s", exc)
        return dict(_EMPTY_RESULT, engine="tesseract")

    words: list[str] = []
    conf_values: list[float] = []

    for word, conf in zip(data.get("text", []), data.get("conf", [])):
        word = (word or "").strip()
        try:
            conf_int = int(conf)
        except (ValueError, TypeError):
            conf_int = -1

        # Tesseract uses -1 to mark non-word rows (e.g. block/line markers).
        if conf_int >= 0 and word:
            words.append(word)
            conf_values.append(float(conf_int))

    full_text = " ".join(words)
    word_count = len(words)
    avg_confidence = (sum(conf_values) / len(conf_values)) if conf_values else 0.0

    return {
        "text": full_text,
        "language": _DEFAULT_LANG,
        "confidence": round(avg_confidence, 2),
        "word_count": word_count,
        "engine": "tesseract",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Result selector
# ─────────────────────────────────────────────────────────────────────────────


def extract_text(
    image: Image.Image,
    paddle_instance: Any | None,
) -> dict[str, Any]:
    """Select the best OCR result from available engines.

    Decision logic:
      1. Try PaddleOCR (if the instance was provided and the library is
         available).
      2. If the Paddle result has ``confidence < OCR_CONFIDENCE_THRESHOLD``
         **or** ``word_count < OCR_MIN_WORDS``, also run Tesseract.
      3. Return whichever result has the higher confidence × word_count score
         (a simple heuristic that prefers richer results).

    Args:
        image:           Pre-processed PIL ``Image`` (RGB).
        paddle_instance: Initialised ``PaddleOCR`` or ``None`` for
                         Tesseract-only mode.

    Returns:
        Best result dict with keys:
        ``text``, ``language``, ``confidence``, ``word_count``, ``engine``.
    """
    paddle_result: dict[str, Any] | None = None

    # ── Step 1: Try PaddleOCR ────────────────────────────────────────────────
    if paddle_instance is not None and PADDLE_AVAILABLE:
        paddle_result = _run_paddleocr(image, paddle_instance)
        logger.debug(
            "PaddleOCR: confidence=%.1f word_count=%d",
            paddle_result["confidence"],
            paddle_result["word_count"],
        )

    # ── Step 2: Decide whether to run Tesseract fallback ────────────────────
    needs_fallback = (
        paddle_result is None
        or paddle_result["confidence"] < OCR_CONFIDENCE_THRESHOLD
        or paddle_result["word_count"] < OCR_MIN_WORDS
    )

    tess_result: dict[str, Any] | None = None
    if needs_fallback and TESSERACT_AVAILABLE:
        tess_result = _run_tesseract(image)
        logger.debug(
            "Tesseract: confidence=%.1f word_count=%d",
            tess_result["confidence"],
            tess_result["word_count"],
        )

    # ── Step 3: Select best result ───────────────────────────────────────────
    # Score = confidence × word_count — penalises both low-confidence and
    # low-volume results.  An empty result scores 0 so a filled result always
    # wins.
    def _score(r: dict[str, Any] | None) -> float:
        if r is None:
            return 0.0
        return r["confidence"] * r["word_count"]

    if _score(tess_result) > _score(paddle_result):
        best = tess_result
    elif paddle_result is not None:
        best = paddle_result
    elif tess_result is not None:
        best = tess_result
    else:
        best = dict(_EMPTY_RESULT)

    logger.info(
        "extract_text selected engine=%s confidence=%.1f words=%d",
        best["engine"],
        best["confidence"],
        best["word_count"],
    )
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Single-image processor
# ─────────────────────────────────────────────────────────────────────────────


def process_image_ocr(
    conn: sqlite3.Connection,
    image_id: int,
    image_path: Path,
    paddle_instance: Any | None,
) -> str:
    """Open, preprocess, OCR, and persist the result for a single image.

    The function is intentionally defensive:
    * Any exception is caught, logged, and recorded as ``'ocr_failed'`` in
      the database so the pipeline can continue with the remaining images.
    * The connection is left open and uncommitted — the caller controls
      checkpoint/commit frequency.

    Args:
        conn:            Open SQLite connection.
        image_id:        Primary key of the ``images`` row.
        image_path:      Absolute path to the image file (never modified).
        paddle_instance: Initialised ``PaddleOCR`` or ``None``.

    Returns:
        ``"success"`` if OCR completed and the result was saved,
        ``"failed"``  if any error occurred.
    """
    try:
        # ── Load original image ──────────────────────────────────────────────
        with Image.open(image_path) as raw:
            # Ensure image data is loaded before the context manager closes.
            raw.load()
            # PIL images are lazy; convert to RGB to detach from file handle.
            original: Image.Image = raw.convert("RGB")

        # ── Preprocess for OCR ───────────────────────────────────────────────
        prepared: Image.Image = enhance_for_ocr(original)

        # ── Run OCR engines ──────────────────────────────────────────────────
        result = extract_text(prepared, paddle_instance)

        # ── Persist result ───────────────────────────────────────────────────
        save_ocr_result(
            conn,
            image_id=image_id,
            text=result["text"],
            language=result["language"],
            confidence=result["confidence"],
            engine=result["engine"],
            word_count=result["word_count"],
        )

        logger.debug(
            "process_image_ocr success: image_id=%d engine=%s words=%d",
            image_id,
            result["engine"],
            result["word_count"],
        )
        return "success"

    except Exception as exc:  # noqa: BLE001
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error(
            "process_image_ocr failed: image_id=%d path=%s — %s",
            image_id,
            image_path,
            err_msg,
            exc_info=True,
        )
        save_ocr_failed(conn, image_id=image_id, error_msg=err_msg)
        return "failed"


# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────


def run_ocr(
    conn: sqlite3.Connection,
    limit: int | None = None,
    force: bool = False,
    retry_failed: bool = False,
) -> dict[str, Any]:
    """Run OCR over all pending (or failed) images in the database.

    PaddleOCR is initialised **once** here (the model loads ~400 MB into RAM
    on first use) and reused for every image in the batch.  This is
    significantly cheaper than re-instantiating per image.

    Checkpointing
    ─────────────
    The database is committed every ``CHECKPOINT_INTERVAL`` images so that a
    crash loses at most that many results rather than the whole batch.

    Args:
        conn:         Open SQLite connection.
        limit:        Maximum images to process (``None`` = all).
        force:        If ``True``, re-process images that already have an OCR
                      result (clears the existing ``ocr_results`` row first).
        retry_failed: If ``True``, include images whose status is
                      ``'ocr_failed'`` in the work queue.

    Returns:
        A statistics dict with keys:
        ``total``, ``success``, ``failed``, ``avg_confidence``, ``elapsed_s``.
    """
    start_time = time.monotonic()

    # ── Build work queue ─────────────────────────────────────────────────────
    if force:
        # Clear existing OCR results so get_pending_images will re-queue them.
        conn.execute("DELETE FROM ocr_results")
        conn.execute("UPDATE images SET status = 'pending' WHERE status = 'ocr_done'")
        conn.commit()
        logger.info("--force: cleared existing OCR results")

    pending = get_pending_images(conn, limit=limit)

    if retry_failed:
        failed_imgs = get_failed_images(conn, limit=None)
        # Reset status to 'pending' so they pass the get_pending_images filter.
        for img in failed_imgs:
            conn.execute(
                "UPDATE images SET status = 'pending' WHERE id = ?", (img["id"],)
            )
        conn.commit()
        # Re-fetch to include the newly re-queued images (honour original limit).
        pending = get_pending_images(conn, limit=limit)

    total = len(pending)
    logger.info(
        "run_ocr: %d image(s) to process (force=%s retry_failed=%s limit=%s)",
        total,
        force,
        retry_failed,
        limit,
    )

    if total == 0:
        logger.info("run_ocr: nothing to do — exiting early.")
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "avg_confidence": 0.0,
            "elapsed_s": round(time.monotonic() - start_time, 2),
        }

    # ── Initialise PaddleOCR once (expensive) ────────────────────────────────
    paddle_instance: Any | None = None
    if PADDLE_AVAILABLE:
        try:
            logger.info("Initialising PaddleOCR (lang=%s) …", PADDLE_LANG)
            paddle_instance = _PaddleOCR(
                use_angle_cls=True,
                lang=PADDLE_LANG,
                show_log=False,
            )
            logger.info("PaddleOCR ready.")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PaddleOCR initialisation failed (%s) — using Tesseract only.", exc
            )
    else:
        logger.info("PaddleOCR not installed — running in Tesseract-only mode.")

    if not TESSERACT_AVAILABLE and paddle_instance is None:
        logger.error(
            "No OCR engine available (PaddleOCR and pytesseract both missing). "
            "Install at least one and retry."
        )
        return {
            "total": total,
            "success": 0,
            "failed": total,
            "avg_confidence": 0.0,
            "elapsed_s": round(time.monotonic() - start_time, 2),
        }

    # ── Process images with tqdm progress bar ────────────────────────────────
    success_count = 0
    failed_count = 0
    confidence_total = 0.0
    pending_since_commit = 0

    with tqdm(
        pending,
        total=total,
        desc="OCR",
        unit="img",
        dynamic_ncols=True,
    ) as bar:
        for img_row in bar:
            image_id: int = img_row["id"]
            image_path = Path(img_row["original_path"])

            outcome = process_image_ocr(
                conn=conn,
                image_id=image_id,
                image_path=image_path,
                paddle_instance=paddle_instance,
            )

            if outcome == "success":
                success_count += 1
                # Retrieve the saved confidence for stats accumulation.
                row = conn.execute(
                    "SELECT confidence FROM ocr_results WHERE image_id = ?",
                    (image_id,),
                ).fetchone()
                if row:
                    confidence_total += row["confidence"]
            else:
                failed_count += 1

            pending_since_commit += 1
            bar.set_postfix(
                ok=success_count,
                fail=failed_count,
                refresh=False,
            )

            # Periodic checkpoint — bounds transaction size.
            if pending_since_commit >= CHECKPOINT_INTERVAL:
                conn.commit()
                pending_since_commit = 0
                logger.debug(
                    "checkpoint commit — processed %d so far",
                    success_count + failed_count,
                )

    # ── Final commit for the remaining batch ─────────────────────────────────
    conn.commit()

    avg_confidence = (
        confidence_total / success_count if success_count > 0 else 0.0
    )
    elapsed = round(time.monotonic() - start_time, 2)

    logger.info(
        "run_ocr complete — total=%d success=%d failed=%d "
        "avg_confidence=%.1f elapsed=%.1fs",
        total,
        success_count,
        failed_count,
        avg_confidence,
        elapsed,
    )

    return {
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "avg_confidence": round(avg_confidence, 2),
        "elapsed_s": elapsed,
    }
