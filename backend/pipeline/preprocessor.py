"""
backend/pipeline/preprocessor.py
─────────────────────────────────
Image pre-processing utilities that improve OCR accuracy.

Two public helpers:
  - is_dark_mode(image)   — heuristic: mean brightness < 100 → dark UI
  - enhance_for_ocr(image) — returns a *new* PIL Image ready for OCR;
                             the original is never mutated.

Pipeline applied by enhance_for_ocr
────────────────────────────────────
  1. Convert to RGB (handles RGBA, palette, L, etc.)
  2. Convert to grayscale (L)
  3. Invert if dark-mode (white text → black text for OCR engines)
  4. Upscale 2× with LANCZOS if width < 1 200 px (boosts small mobile shots)
  5. Sharpen once (ImageFilter.SHARPEN)
  6. Convert back to RGB so downstream code always receives a 3-channel image
"""

from __future__ import annotations

from PIL import Image, ImageFilter, ImageOps


# ─────────────────────────────────────────────────────────────────────────────
# Thresholds / constants
# ─────────────────────────────────────────────────────────────────────────────

#: Mean pixel brightness (0–255 scale) below which the screenshot is treated
#: as a dark-mode / inverted UI.
DARK_MODE_THRESHOLD: int = 100

#: Minimum width (pixels) below which the image is upscaled 2× before OCR.
MIN_OCR_WIDTH: int = 1_200

#: Scale factor applied to narrow images.
UPSCALE_FACTOR: int = 2


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────


def is_dark_mode(image: Image.Image) -> bool:
    """Return *True* when the image appears to use a dark colour scheme.

    Uses the mean luminance of the grayscale representation as a cheap
    proxy.  A threshold of 100 (out of 255) correctly identifies most
    dark-mode UIs, OLED wallpapers, and inverted screenshots.

    Args:
        image: Any PIL ``Image`` object (mode is handled internally).

    Returns:
        ``True`` if average brightness < :data:`DARK_MODE_THRESHOLD`.
    """
    # Convert to grayscale for a single-channel mean; stat() is fast.
    gray = image.convert("L")
    # ImageStat.Stat().mean returns a list; index 0 is the L channel.
    from PIL import ImageStat
    mean_brightness: float = ImageStat.Stat(gray).mean[0]
    return mean_brightness < DARK_MODE_THRESHOLD


def enhance_for_ocr(image: Image.Image) -> Image.Image:
    """Return a pre-processed copy of *image* optimised for OCR engines.

    The original ``Image`` object is **never** mutated.  Every step
    operates on a fresh copy so callers may pass a cached image safely.

    Processing steps
    ----------------
    1. **RGB normalisation** — converts any mode (RGBA, P, L …) to RGB.
    2. **Grayscale** — reduces colour variation that confuses OCR.
    3. **Dark-mode inversion** — if the mean brightness is below
       :data:`DARK_MODE_THRESHOLD`, pixels are inverted so that white
       text on a dark background becomes black text on white.
    4. **Upscaling** — if the image width is below :data:`MIN_OCR_WIDTH`,
       the image is scaled up by :data:`UPSCALE_FACTOR` using the
       high-quality LANCZOS resampling filter.
    5. **Sharpening** — one pass of ``ImageFilter.SHARPEN`` improves
       character edge definition without introducing ringing artefacts.
    6. **Back to RGB** — returns a 3-channel image so that downstream
       code (PaddleOCR, pytesseract, classifier) all receive the same
       predictable format.

    Args:
        image: Source PIL ``Image`` in any mode.

    Returns:
        A new :class:`PIL.Image.Image` in ``"RGB"`` mode, ready for OCR.
    """
    # Step 1 — Normalise to RGB (handles RGBA, palette, 1-bit, etc.)
    enhanced: Image.Image = image.convert("RGB")

    # Step 2 — Convert to grayscale for uniform processing
    enhanced = enhanced.convert("L")

    # Step 3 — Invert dark-mode screenshots so text becomes dark on light
    #           We test on the grayscale copy that is already in hand.
    if _mean_brightness(enhanced) < DARK_MODE_THRESHOLD:
        enhanced = ImageOps.invert(enhanced)

    # Step 4 — Upscale narrow images (e.g. portrait mobile screenshots)
    if enhanced.width < MIN_OCR_WIDTH:
        new_width = enhanced.width * UPSCALE_FACTOR
        new_height = enhanced.height * UPSCALE_FACTOR
        enhanced = enhanced.resize(
            (new_width, new_height),
            resample=Image.Resampling.LANCZOS,
        )

    # Step 5 — One sharpening pass to improve character edge definition
    enhanced = enhanced.filter(ImageFilter.SHARPEN)

    # Step 6 — Return as RGB so callers always receive a 3-channel image
    return enhanced.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _mean_brightness(gray_image: Image.Image) -> float:
    """Return the mean pixel value of a single-channel (``"L"`` mode) image.

    Args:
        gray_image: A PIL ``Image`` already in ``"L"`` mode.

    Returns:
        Mean brightness as a float in the range [0.0, 255.0].
    """
    from PIL import ImageStat
    return ImageStat.Stat(gray_image).mean[0]
