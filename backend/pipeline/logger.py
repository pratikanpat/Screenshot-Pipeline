"""
backend/pipeline/logger.py
───────────────────────────
Logging factory for the ingestion pipeline.

``setup_logger`` creates a named :class:`logging.Logger` that writes to:
  - A rotating file (INFO level and above, UTF-8, up to 5 MB, 3 backups)
  - stdout via StreamHandler (WARNING level and above)

Using separate level thresholds keeps the console quiet during normal
operation while the log file retains full detail for post-hoc debugging.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

#: Maximum size of a single log file before rotation (5 MB).
LOG_MAX_BYTES: int = 5 * 1024 * 1024

#: Number of rotated backup files to keep alongside the active log.
LOG_BACKUP_COUNT: int = 3

#: Format string shared by both handlers.
_LOG_FORMAT: str = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

#: Date/time format for log records.
_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def setup_logger(name: str, log_file: Path) -> logging.Logger:
    """Create and return a configured :class:`logging.Logger`.

    The returned logger writes to two destinations:

    1. **Rotating file** at *log_file* — level ``INFO`` and above.
       Rotates when the file exceeds :data:`LOG_MAX_BYTES`; at most
       :data:`LOG_BACKUP_COUNT` backup files are kept.  File is opened in
       UTF-8 mode so non-ASCII paths and OCR text round-trip cleanly.

    2. **Standard output** (``sys.stdout``) — level ``WARNING`` and above.
       Keeps console output concise; INFO/DEBUG chatter stays in the file.

    The logger's own level is set to ``DEBUG`` so that both handlers can
    filter independently without being blocked at the logger level.

    If the parent directory of *log_file* does not exist it is created
    automatically (``mkdir -p`` semantics).

    Re-entrancy note
    ────────────────
    Calling ``setup_logger`` with the same *name* twice returns the
    **same** Python logger object (the standard ``logging`` module caches
    by name).  To avoid duplicate handlers, the function checks whether
    the logger already has handlers and returns early if so.

    Args:
        name:     Logger name, typically ``__name__`` of the calling module.
        log_file: Absolute or relative path to the log file.

    Returns:
        A fully configured :class:`logging.Logger` instance.

    Example::

        log = setup_logger("pipeline.ingestion", Path("data/logs/ingestion.log"))
        log.info("Starting ingestion run")
    """
    # Ensure the log directory exists before the RotatingFileHandler tries to
    # open the file — avoids FileNotFoundError on first run.
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    # Guard against double-registration when the module is imported multiple
    # times (e.g. during pytest collection or reload).
    if logger.handlers:
        return logger

    # Allow all levels through the logger; each handler filters independently.
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # ── Rotating file handler (INFO+) ─────────────────────────────────────
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ── stdout handler (WARNING+) ─────────────────────────────────────────
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
