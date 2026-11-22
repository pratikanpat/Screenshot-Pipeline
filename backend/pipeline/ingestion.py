"""
backend/pipeline/ingestion.py
──────────────────────────────
Core ingestion pipeline: scan a screenshot folder, hash every file,
skip already-indexed images (resume support), and insert new records
into the ``images`` table with status ``'pending'``.

Public API
──────────
  calculate_sha256(path)          → hex string
  extract_capture_date(filename)  → ISO-8601 string | None
  read_image_metadata(path)       → dict(width, height, format, error)
  scan_folder(source)             → sorted list[Path]
  process_one(conn, file_path, source) → "ok" | "error" | "skipped"
  run_ingestion(source, limit, conn)   → dict(total, ok, error, skipped)
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

from backend.config import (
    HASH_CHUNK_SIZE,
    SUPPORTED_EXTENSIONS,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

#: Number of files processed between SQLite commits.  Keeps transactions
#: short while avoiding a commit-per-file overhead.
CHECKPOINT_INTERVAL: int = 50

# Regex patterns that recognise common screenshot filename conventions.
# Group 1 always holds the date/time digits; we normalise to ISO-8601.
_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Screenshot_20261121-164334  →  2026-11-21T16:43:34
    (
        re.compile(
            r"Screenshot[_ ](\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})",
            re.IGNORECASE,
        ),
        "compact",
    ),
    # Screenshot 2026-11-22 024257  →  2026-11-22T02:42:57
    (
        re.compile(
            r"Screenshot[_ ](\d{4})-(\d{2})-(\d{2})[_ ](\d{2})(\d{2})(\d{2})",
            re.IGNORECASE,
        ),
        "dashed",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# File hashing
# ─────────────────────────────────────────────────────────────────────────────


def calculate_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file using chunked reads.

    Reading in fixed-size chunks (default 1 MB, see
    :data:`backend.config.HASH_CHUNK_SIZE`) keeps memory usage constant
    even for very large files.

    Args:
        path: Absolute (or resolvable) :class:`pathlib.Path` to the file.

    Returns:
        Lower-case hex-encoded SHA-256 string (64 characters).

    Raises:
        OSError: If the file cannot be opened or read.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(HASH_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Filename date extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_capture_date(filename: str) -> str | None:
    """Parse a screenshot filename and return an ISO-8601 datetime string.

    Recognised patterns
    ───────────────────
    - ``Screenshot_20261121-164334``   → ``2026-11-21T16:43:34``
    - ``Screenshot 2026-11-22 024257`` → ``2026-11-22T02:42:57``

    The function is intentionally liberal: it only looks for a known
    prefix followed by digits; surrounding noise (app name, suffix …)
    is ignored.

    Args:
        filename: Bare filename (with or without extension).

    Returns:
        ISO-8601 string (``YYYY-MM-DDTHH:MM:SS``) or ``None`` if no
        recognisable date pattern is found.
    """
    stem = Path(filename).stem  # strip extension for cleaner matching

    for pattern, _fmt in _DATE_PATTERNS:
        m = pattern.search(stem)
        if m:
            year, month, day, hour, minute, second = m.groups()
            try:
                dt = datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute), int(second),
                )
                return dt.isoformat()
            except ValueError:
                # Groups matched but digits form an invalid date — skip.
                logger.debug(
                    "Date digits from '%s' are out of range; skipping.", filename
                )
                continue

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Image metadata
# ─────────────────────────────────────────────────────────────────────────────


def read_image_metadata(path: Path) -> dict[str, Any]:
    """Open an image with Pillow and return basic metadata.

    The function never raises; any error is captured in the ``"error"``
    key so callers can decide whether to skip or flag the file.

    Args:
        path: Path to the image file.

    Returns:
        A dict with keys:
          - ``width``  (int | None)
          - ``height`` (int | None)
          - ``format`` (str | None) — e.g. ``"PNG"``, ``"JPEG"``
          - ``error``  (str | None) — exception message if opening failed
    """
    result: dict[str, Any] = {
        "width": None,
        "height": None,
        "format": None,
        "error": None,
    }
    try:
        with Image.open(path) as img:
            result["width"] = img.width
            result["height"] = img.height
            result["format"] = img.format  # None for in-memory images
    except UnidentifiedImageError as exc:
        result["error"] = f"UnidentifiedImageError: {exc}"
    except OSError as exc:
        result["error"] = f"OSError: {exc}"
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Folder scanning
# ─────────────────────────────────────────────────────────────────────────────


def scan_folder(source: Path) -> list[Path]:
    """Return a sorted list of image files found under *source*.

    Only files whose suffix (lower-cased) is in
    :data:`backend.config.SUPPORTED_EXTENSIONS` are returned.  The list
    is sorted by filename so runs are deterministic.

    Args:
        source: Root directory to scan (non-recursive by design — the
                screenshot library is a flat folder in practice).

    Returns:
        Sorted :class:`list` of :class:`pathlib.Path` objects.

    Raises:
        FileNotFoundError: If *source* does not exist.
        NotADirectoryError: If *source* is not a directory.
    """
    if not source.exists():
        raise FileNotFoundError(f"Source folder not found: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source}")

    files: list[Path] = [
        f
        for f in source.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort(key=lambda p: p.name)
    logger.info("scan_folder: found %d image(s) in '%s'", len(files), source)
    return files


# ─────────────────────────────────────────────────────────────────────────────
# Single-file processing
# ─────────────────────────────────────────────────────────────────────────────


def process_one(
    conn: sqlite3.Connection,
    file_path: Path,
    source: Path,
) -> str:
    """Ingest a single image file into the database.

    Resume support
    ──────────────
    Before inserting, the function checks whether a row with the same
    ``original_path`` already exists in the ``images`` table.  If the
    stored ``sha256`` **and** ``modified_at_ns`` both match the current
    file, the file is skipped (``"skipped"`` return value) — the pipeline
    can be interrupted and restarted without re-processing unchanged files.

    If only ``sha256`` matches but ``modified_at_ns`` differs, the file
    has been re-saved (touch / re-export) and is treated as new; the old
    row is **not** deleted (deduplication is handled downstream).

    Args:
        conn:      Open :class:`sqlite3.Connection` to the knowledge-base.
        file_path: Absolute path to the image file.
        source:    Root source directory (used only for logging context).

    Returns:
        ``"ok"``      — row inserted successfully.
        ``"skipped"`` — file already in DB with identical hash + mtime.
        ``"error"``   — an exception occurred; details logged at ERROR level.
    """
    try:
        # ── File system stats ────────────────────────────────────────────
        stat = file_path.stat()
        file_size: int = stat.st_size
        modified_at_ns: int = stat.st_mtime_ns
        modified_at: str = datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat()

        # ── Resume check ─────────────────────────────────────────────────
        # Look up existing row by absolute path (the UNIQUE column).
        existing = conn.execute(
            "SELECT sha256, modified_at_ns FROM images WHERE original_path = ?",
            (str(file_path),),
        ).fetchone()

        if existing is not None:
            # Row already exists — compute hash only if mtime changed.
            if existing["modified_at_ns"] == modified_at_ns:
                # Fast path: mtime identical → assume unchanged, skip.
                logger.debug("skip (mtime match): %s", file_path.name)
                return "skipped"

            # mtime changed → verify hash to detect actual modification.
            current_sha = calculate_sha256(file_path)
            if existing["sha256"] == current_sha:
                # Same bytes, only touch-timestamp changed → still skip.
                logger.debug("skip (sha256 match, mtime drift): %s", file_path.name)
                return "skipped"

            # File genuinely changed; fall through to insert a new row.
            logger.info("re-ingesting modified file: %s", file_path.name)

        # ── Hash ─────────────────────────────────────────────────────────
        sha256: str = calculate_sha256(file_path)

        # ── Image metadata ───────────────────────────────────────────────
        meta = read_image_metadata(file_path)

        # ── Filename-based capture date ──────────────────────────────────
        captured_at: str | None = extract_capture_date(file_path.name)

        # ── Insert row ───────────────────────────────────────────────────
        conn.execute(
            """
            INSERT INTO images (
                filename, original_path, sha256, file_size,
                width, height, image_format,
                captured_at, modified_at, modified_at_ns,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                file_path.name,
                str(file_path),
                sha256,
                file_size,
                meta["width"],
                meta["height"],
                meta["format"],
                captured_at,
                modified_at,
                modified_at_ns,
            ),
        )
        logger.debug("inserted: %s (sha256=%.8s…)", file_path.name, sha256)
        return "ok"

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "process_one failed for '%s': %s: %s",
            file_path.name,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return "error"


# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────


def run_ingestion(
    source: Path,
    limit: int | None,
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """Scan *source* and ingest every image into *conn*.

    Features
    ────────
    - tqdm progress bar printed to stdout.
    - Commits every :data:`CHECKPOINT_INTERVAL` files so a crash loses
      at most that many inserts.
    - Respects *limit* when set (useful for smoke-tests).

    Args:
        source: Directory containing screenshot files.
        limit:  Maximum number of files to process (``None`` = all).
        conn:   Open SQLite connection; the caller owns its lifecycle.

    Returns:
        A dict with integer keys:
          ``total``   — files discovered (after limit applied),
          ``ok``      — successfully inserted,
          ``error``   — failed to process,
          ``skipped`` — already present in DB with identical content.
    """
    all_files = scan_folder(source)

    if limit is not None and limit > 0:
        all_files = all_files[:limit]

    total = len(all_files)
    counts: dict[str, int] = {"total": total, "ok": 0, "error": 0, "skipped": 0}

    logger.info(
        "run_ingestion: processing %d file(s) from '%s'", total, source
    )

    pending_since_commit = 0

    with tqdm(
        all_files,
        total=total,
        desc="Ingesting",
        unit="img",
        dynamic_ncols=True,
    ) as bar:
        for file_path in bar:
            result = process_one(conn, file_path, source)
            counts[result] += 1
            pending_since_commit += 1
            bar.set_postfix(
                ok=counts["ok"],
                skip=counts["skipped"],
                err=counts["error"],
                refresh=False,
            )

            # Periodic commit — keeps transaction size bounded.
            if pending_since_commit >= CHECKPOINT_INTERVAL:
                conn.commit()
                pending_since_commit = 0
                logger.debug("checkpoint commit at %d files", counts["ok"] + counts["skipped"])

    # Final commit for the remaining batch.
    conn.commit()

    logger.info(
        "run_ingestion complete — total=%d ok=%d skipped=%d error=%d",
        counts["total"],
        counts["ok"],
        counts["skipped"],
        counts["error"],
    )
    return counts
