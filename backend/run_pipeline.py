"""
backend/run_pipeline.py
────────────────────────
CLI entry-point for the Screenshot Knowledge Base ingestion pipeline.

Commands
────────
  ingest  — scan a source folder and insert new images into the database
  status  — print a summary of the pipeline state from the database

Usage examples
──────────────
  # Ingest all screenshots from the default source
  python -m backend.run_pipeline ingest

  # Ingest from a custom folder, limit to 100 files, use a custom DB
  python -m backend.run_pipeline ingest --source ~/Pictures --limit 100 --db ./data/library.db

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
# Entry-point guard
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
