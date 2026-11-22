"""
backend/run_pipeline.py
────────────────────────
CLI entry-point for the Screenshot Knowledge Base pipeline.

Commands
────────
  ingest  — scan a source folder and insert new images into the database
  status  — print a summary of the pipeline state from the database
  ocr     — run OCR over all pending images (PaddleOCR primary, Tesseract fallback)

Usage examples
──────────────
  # Ingest all screenshots from the default source
  python -m backend.run_pipeline ingest

  # Ingest from a custom folder, limit to 100 files, use a custom DB
  python -m backend.run_pipeline ingest --source ~/Pictures --limit 100 --db ./data/library.db

  # Run OCR on all pending images
  python -m backend.run_pipeline ocr

  # OCR first 20 images, with a custom DB path
  python -m backend.run_pipeline ocr --limit 20 --db ./data/library.db

  # Re-process images that previously failed
  python -m backend.run_pipeline ocr --retry-failed

  # Force re-run OCR on every image (clears existing results)
  python -m backend.run_pipeline ocr --force

  # Print DB status
  python -m backend.run_pipeline status --db ./data/library.db
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from backend.config import DATABASE, DEFAULT_SOURCE, LOGS_DIR
from backend.db.database import get_connection
from backend.pipeline.ingestion import run_ingestion
from backend.pipeline.logger import setup_logger
from backend.pipeline.ocr import run_ocr

# ─────────────────────────────────────────────────────────────────────────────
# Module-level logger (WARNING+ to console, INFO+ to file)
# ─────────────────────────────────────────────────────────────────────────────

_log = setup_logger("run_pipeline", LOGS_DIR / "pipeline.log")

# ─────────────────────────────────────────────────────────────────────────────
# Shared banner
# ─────────────────────────────────────────────────────────────────────────────

_BANNER = r"""
╔══════════════════════════════════════════════════════╗
║       Screenshot Knowledge Base — Pipeline v2        ║
╚══════════════════════════════════════════════════════╝
"""


def _print_banner() -> None:
    """Print the CLI banner to stdout."""
    click.echo(_BANNER)


# ─────────────────────────────────────────────────────────────────────────────
# CLI group
# ─────────────────────────────────────────────────────────────────────────────


@click.group()
def cli() -> None:
    """Screenshot Knowledge Base — pipeline management CLI.

    Run a sub-command with --help for more information.
    """


# ─────────────────────────────────────────────────────────────────────────────
# `ingest` command
# ─────────────────────────────────────────────────────────────────────────────


@cli.command("ingest")
@click.option(
    "--source",
    "source_path",
    default=str(DEFAULT_SOURCE),
    show_default=True,
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=str),
    help="Directory containing source screenshots (never modified).",
)
@click.option(
    "--limit",
    default=None,
    type=int,
    show_default=True,
    help="Maximum number of files to process (omit for all).",
)
@click.option(
    "--db",
    "db_path",
    default=str(DATABASE),
    show_default=True,
    type=click.Path(path_type=str),
    help="Path to the SQLite database file.",
)
def ingest(source_path: str, limit: int | None, db_path: str) -> None:
    """Scan SOURCE and ingest new screenshots into the database.

    Files already present (same SHA-256 + mtime) are skipped so the
    command is safe to run repeatedly without duplicating records.
    """
    _print_banner()

    source = Path(source_path)
    db = Path(db_path)

    click.echo(f"  Source  : {source}")
    click.echo(f"  Database: {db}")
    if limit:
        click.echo(f"  Limit   : {limit} file(s)")
    click.echo()

    # Validate source directory before opening DB.
    if not source.exists():
        click.secho(f"ERROR: source folder does not exist: {source}", fg="red", err=True)
        sys.exit(1)

    _log.info("ingest command started — source=%s limit=%s db=%s", source, limit, db)

    try:
        conn = get_connection(db)
    except Exception as exc:  # noqa: BLE001
        click.secho(f"ERROR: could not open database: {exc}", fg="red", err=True)
        _log.error("Failed to open database '%s': %s", db, exc, exc_info=True)
        sys.exit(1)

    try:
        counts = run_ingestion(source=source, limit=limit, conn=conn)
    except FileNotFoundError as exc:
        click.secho(f"ERROR: {exc}", fg="red", err=True)
        _log.error("Ingestion aborted: %s", exc)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        click.secho(f"ERROR: unexpected failure: {exc}", fg="red", err=True)
        _log.error("Unexpected ingestion error: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        conn.close()

    # ── Summary ──────────────────────────────────────────────────────────────
    click.echo()
    click.secho("  ── Ingestion Summary ──────────────────────────", fg="cyan")
    click.echo(f"  Total discovered : {counts['total']}")
    click.secho(f"  Inserted (ok)    : {counts['ok']}", fg="green")
    click.secho(f"  Skipped          : {counts['skipped']}", fg="yellow")
    click.secho(
        f"  Errors           : {counts['error']}",
        fg="red" if counts["error"] else "white",
    )
    click.echo()

    _log.info(
        "ingest complete — total=%d ok=%d skipped=%d error=%d",
        counts["total"], counts["ok"], counts["skipped"], counts["error"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# `status` command
# ─────────────────────────────────────────────────────────────────────────────


@cli.command("status")
@click.option(
    "--db",
    "db_path",
    default=str(DATABASE),
    show_default=True,
    type=click.Path(path_type=str),
    help="Path to the SQLite database file.",
)
def status(db_path: str) -> None:
    """Print a summary of the current pipeline state from the database."""
    _print_banner()

    db = Path(db_path)
    click.echo(f"  Database: {db}")
    click.echo()

    if not db.exists():
        click.secho("  Database file not found — has ingestion been run yet?", fg="yellow")
        sys.exit(0)

    try:
        conn = get_connection(db)
    except Exception as exc:  # noqa: BLE001
        click.secho(f"ERROR: could not open database: {exc}", fg="red", err=True)
        sys.exit(1)

    try:
        # Total images in the library.
        row_total = conn.execute("SELECT COUNT(*) AS n FROM images").fetchone()
        total: int = row_total["n"] if row_total else 0

        # Per-status breakdown.
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM images GROUP BY status ORDER BY status"
        ).fetchall()
        status_counts: dict[str, int] = {r["status"]: r["n"] for r in rows}

    except Exception as exc:  # noqa: BLE001
        click.secho(f"ERROR: query failed: {exc}", fg="red", err=True)
        sys.exit(1)
    finally:
        conn.close()

    # Convenience aliases with defaults of 0.
    pending: int   = status_counts.get("pending", 0)
    processed: int = status_counts.get("indexed", 0)
    failed: int    = status_counts.get("error", 0)

    click.secho("  ── Database Status ─────────────────────────────", fg="cyan")
    click.echo(f"  Total images     : {total}")
    click.secho(f"  Pending          : {pending}", fg="yellow")
    click.secho(f"  Processed/indexed: {processed}", fg="green")
    click.secho(
        f"  Failed           : {failed}",
        fg="red" if failed else "white",
    )

    # Print any extra statuses that exist (e.g. "processing" from a crash).
    for st, count in status_counts.items():
        if st not in {"pending", "indexed", "error"}:
            click.echo(f"  {st:<17}: {count}")

    click.echo()


# ─────────────────────────────────────────────────────────────────────────────
# `ocr` command
# ─────────────────────────────────────────────────────────────────────────────


@cli.command("ocr")
@click.option(
    "--limit",
    default=None,
    type=int,
    show_default=True,
    help="Maximum number of images to OCR (omit for all pending).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-process images that already have an OCR result (clears existing results).",
)
@click.option(
    "--retry-failed",
    "retry_failed",
    is_flag=True,
    default=False,
    help="Also retry images whose OCR previously failed.",
)
@click.option(
    "--db",
    "db_path",
    default=str(DATABASE),
    show_default=True,
    type=click.Path(path_type=str),
    help="Path to the SQLite database file.",
)
def ocr_cmd(
    limit: int | None,
    force: bool,
    retry_failed: bool,
    db_path: str,
) -> None:
    """Run OCR over all pending images using PaddleOCR (primary) and
    Tesseract (fallback).

    PaddleOCR is initialised once per batch run to avoid repeatedly loading
    the ~400 MB model.  Results are checkpointed every CHECKPOINT_INTERVAL
    images so a crash loses at most that many results.

    Use --force to re-run OCR on images that were already processed, or
    --retry-failed to retry images that previously errored out.
    """
    _print_banner()

    db = Path(db_path)

    click.echo(f"  Database     : {db}")
    if limit:
        click.echo(f"  Limit        : {limit} image(s)")
    if force:
        click.secho("  Mode         : FORCE (existing results will be cleared)", fg="yellow")
    if retry_failed:
        click.secho("  Retry failed : ON", fg="yellow")
    click.echo()

    _log.info(
        "ocr command started — db=%s limit=%s force=%s retry_failed=%s",
        db, limit, force, retry_failed,
    )

    try:
        conn = get_connection(db)
    except Exception as exc:  # noqa: BLE001
        click.secho(f"ERROR: could not open database: {exc}", fg="red", err=True)
        _log.error("Failed to open database '%s': %s", db, exc, exc_info=True)
        sys.exit(1)

    try:
        stats = run_ocr(
            conn=conn,
            limit=limit,
            force=force,
            retry_failed=retry_failed,
        )
    except Exception as exc:  # noqa: BLE001
        click.secho(f"ERROR: unexpected OCR failure: {exc}", fg="red", err=True)
        _log.error("Unexpected OCR error: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        conn.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    click.echo()
    click.secho("  ── OCR Summary ─────────────────────────────────", fg="cyan")
    click.echo(f"  Total processed  : {stats['total']}")
    click.secho(f"  Succeeded        : {stats['success']}", fg="green")
    click.secho(
        f"  Failed           : {stats['failed']}",
        fg="red" if stats["failed"] else "white",
    )
    click.echo(f"  Avg confidence   : {stats['avg_confidence']:.1f}%")
    click.echo(f"  Elapsed time     : {stats['elapsed_s']:.1f}s")
    click.echo()

    _log.info(
        "ocr complete — total=%d success=%d failed=%d avg_conf=%.1f elapsed=%.1fs",
        stats["total"],
        stats["success"],
        stats["failed"],
        stats["avg_confidence"],
        stats["elapsed_s"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# classify command
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--limit", type=int, default=None, help="Max images to classify.")
@click.option("--force", is_flag=True, help="Re-classify already-classified images.")
@click.option("--db", "db_path", type=click.Path(), default=None,
              help="SQLite database path.")
def classify(limit, force, db_path):
    """Classify screenshots using CLIP zero-shot + keyword rules."""
    from backend.db.database import get_connection
    from backend.pipeline.classifier import run_classification

    db = Path(db_path) if db_path else DATABASE
    conn = get_connection(db)

    _print_banner("CLASSIFIER")
    click.echo(f"  Database : {db}")
    click.echo(f"  Limit    : {limit or 'all'}")
    click.echo(f"  Force    : {force}")
    click.echo()

    stats = run_classification(conn, limit=limit, force=force)
    conn.close()

    click.secho("\n  Classification complete.", fg="green")
    click.echo(f"  Total     : {stats['total']}")
    click.secho(f"  Success   : {stats['success']}", fg="green")
    click.secho(f"  Failed    : {stats['failed']}", fg="red" if stats["failed"] else "white")
    click.echo(f"  Elapsed   : {stats['elapsed_s']:.1f}s")
    click.echo()


# ─────────────────────────────────────────────────────────────────────────────
# embed command
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--limit", type=int, default=None, help="Max images to embed.")
@click.option("--force", is_flag=True, help="Re-embed already embedded images.")
@click.option("--db", "db_path", type=click.Path(), default=None,
              help="SQLite database path.")
def embed(limit, force, db_path):
    """Generate CLIP embeddings and store in ChromaDB for semantic search."""
    from backend.db.database import get_connection
    from backend.pipeline.embeddings import run_embeddings

    db = Path(db_path) if db_path else DATABASE
    conn = get_connection(db)

    _print_banner("EMBEDDINGS")
    click.echo(f"  Database : {db}")
    click.echo()

    stats = run_embeddings(conn, limit=limit, force=force)
    conn.close()

    if stats.get("skipped"):
        click.secho("  Skipped — ChromaDB or CLIP model not available.", fg="yellow")
        return

    click.secho("\n  Embedding complete.", fg="green")
    click.echo(f"  Total   : {stats['total']}")
    click.secho(f"  Success : {stats['success']}", fg="green")
    click.secho(f"  Failed  : {stats['failed']}", fg="red" if stats["failed"] else "white")
    click.echo(f"  Elapsed : {stats['elapsed_s']:.1f}s")
    click.echo()


# ─────────────────────────────────────────────────────────────────────────────
# process-all command  (ingest → ocr → classify → embed in one shot)
# ─────────────────────────────────────────────────────────────────────────────

@cli.command(name="process-all")
@click.option("--source", type=click.Path(exists=True), default=None,
              help="Screenshot source folder.")
@click.option("--limit", type=int, default=None, help="Max images per stage.")
@click.option("--db", "db_path", type=click.Path(), default=None,
              help="SQLite database path.")
def process_all(source, limit, db_path):
    """Run the full pipeline: ingest → OCR → classify → embed."""
    import time as _time
    from backend.db.database import get_connection
    from backend.pipeline.ingestion import run_ingestion
    from backend.pipeline.ocr import run_ocr
    from backend.pipeline.classifier import run_classification
    from backend.pipeline.embeddings import run_embeddings

    db = Path(db_path) if db_path else DATABASE
    src = Path(source) if source else DEFAULT_SOURCE
    conn = get_connection(db)

    _print_banner("FULL PIPELINE")
    click.echo(f"  Source   : {src}")
    click.echo(f"  Database : {db}")
    click.echo(f"  Limit    : {limit or 'all'}")
    click.echo()

    t0 = _time.monotonic()

    click.secho("── Stage 1: Ingest ─────────────────", fg="cyan")
    i_stats = run_ingestion(src, limit, conn)
    click.echo(f"  {i_stats['ok']} ingested, {i_stats['skipped']} skipped, {i_stats['error']} errors\n")

    click.secho("── Stage 2: OCR ────────────────────", fg="cyan")
    o_stats = run_ocr(conn, limit=limit)
    click.echo(f"  {o_stats['success']} ok, {o_stats['failed']} failed, avg_conf={o_stats['avg_confidence']:.1f}%\n")

    click.secho("── Stage 3: Classify ───────────────", fg="cyan")
    c_stats = run_classification(conn, limit=limit)
    click.echo(f"  {c_stats['success']} ok, {c_stats['failed']} failed\n")

    click.secho("── Stage 4: Embed ──────────────────", fg="cyan")
    e_stats = run_embeddings(conn, limit=limit)
    click.echo(f"  {e_stats.get('success', 0)} embedded\n")

    conn.close()
    elapsed = _time.monotonic() - t0
    click.secho(f"✓ Pipeline complete in {elapsed:.1f}s", fg="green", bold=True)
    click.echo()


# ─────────────────────────────────────────────────────────────────────────────
# Entry-point guard
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()