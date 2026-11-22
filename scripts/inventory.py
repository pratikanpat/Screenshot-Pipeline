# What this script will eventually do:
# Operation	           -->  Purpose
# Image scanning	        Discover all screenshots
# SHA-256 hashing       	Identify identical files
# Metadata extraction   	Record dimensions, format and size
# Date extraction	        Identify screenshot timestamps where possible
# SQLite storage	        Save everything in a searchable database
# Error handling	        Record corrupted or unreadable files

# What the script does
# 1. Scans C:\Users\Pratik\Pictures\MobScreenshots.
# 2. Records each image's filename, path, extension, size and dimensions.
# 3. Calculates its SHA-256 hash to identify identical image files.
# 4. Extracts a possible capture date from screenshot filenames.
# 5. Saves records in data\library.db.
# 6. Supports small test runs and full runs.
# 7. Can resume safely if interrupted.
# 8. Never modifies or deletes original screenshots.


from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SOURCE = Path.home() / "Pictures" / "MobScreenshots"
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "library.db"
LOG_FILE = PROJECT_ROOT / "data" / "logs" / "inventory.log"

SUPPORTED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp",
    ".bmp", ".tiff", ".tif", ".gif"
}

HASH_CHUNK_SIZE = 1024 * 1024  # 1 MB


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8"
    )


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def create_database(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            relative_path TEXT UNIQUE NOT NULL,
            original_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            extension TEXT,
            file_size INTEGER,
            width INTEGER,
            height INTEGER,
            image_format TEXT,
            modified_at TEXT,
            modified_at_ns INTEGER,
            captured_at TEXT,
            sha256 TEXT,
            inventory_status TEXT NOT NULL,
            error_message TEXT,
            indexed_at TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_images_sha256
        ON images(sha256)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_images_status
        ON images(inventory_status)
    """)

    connection.commit()


# --------------------------------------------------
# CAPTURE DATE EXTRACTION
# --------------------------------------------------

def extract_capture_date(filename: str) -> str | None:
    """
    Recognizes common screenshot filename patterns.

    Examples:
    Screenshot_20261121-164334.png
    Screenshot 2026-11-22 024257.png

    Returns None when no reliable pattern is found.
    """

    patterns = [
        (r"(\d{8})[-_ ](\d{6})", "%Y%m%d%H%M%S"),
        (r"(\d{4}-\d{2}-\d{2})[ _-](\d{6})",
         "%Y-%m-%d%H%M%S"),
    ]

    for pattern, date_format in patterns:
        match = re.search(pattern, filename)

        if match:
            value = "".join(match.groups())

            try:
                return datetime.strptime(
                    value, date_format
                ).isoformat(sep=" ")

            except ValueError:
                pass

    return None


# --------------------------------------------------
# SHA-256 HASHING
# --------------------------------------------------

def calculate_sha256(file_path: Path) -> str:
    """
    Reads the file in small chunks.
    Does not load the entire image into memory.
    """

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(HASH_CHUNK_SIZE):
            digest.update(chunk)

    return digest.hexdigest()


# --------------------------------------------------
# IMAGE METADATA
# --------------------------------------------------

def read_image_metadata(file_path: Path):
    """
    Reads image dimensions and format.
    Original image is never modified.
    """

    try:
        with Image.open(file_path) as image:
            width, height = image.size
            image_format = image.format
            image.verify()

        return width, height, image_format, None

    except (UnidentifiedImageError, OSError, ValueError) as error:
        return None, None, None, str(error)

    except Exception as error:
        return None, None, None, f"Unexpected error: {error}"


# --------------------------------------------------
# PROCESS ONE IMAGE
# --------------------------------------------------

def process_image(connection, file_path: Path, source: Path):
    relative_path = file_path.relative_to(source).as_posix()
    original_path = str(file_path.resolve())

    stat = file_path.stat()
    file_size = stat.st_size
    modified_at_ns = stat.st_mtime_ns

    modified_at = datetime.fromtimestamp(
        stat.st_mtime
    ).isoformat(sep=" ", timespec="seconds")

    filename = file_path.name
    extension = file_path.suffix.lower()
    captured_at = extract_capture_date(filename)

    # Check whether this file was already inventoried
    previous = connection.execute("""
        SELECT file_size, modified_at_ns, sha256,
               width, height, image_format,
               inventory_status, error_message
        FROM images
        WHERE relative_path = ?
    """, (relative_path,)).fetchone()

    # Reuse previous results if the file has not changed
    if (
        previous
        and previous[0] == file_size
        and previous[1] == modified_at_ns
        and previous[2]
        and previous[6] == "ok"
    ):
        sha256 = previous[2]
        width = previous[3]
        height = previous[4]
        image_format = previous[5]
        status = "ok"
        error_message = None

    else:
        sha256 = calculate_sha256(file_path)

        width, height, image_format, error_message = (
            read_image_metadata(file_path)
        )

        status = "ok" if error_message is None else "error"

    connection.execute("""
        INSERT INTO images (
            relative_path,
            original_path,
            filename,
            extension,
            file_size,
            width,
            height,
            image_format,
            modified_at,
            modified_at_ns,
            captured_at,
            sha256,
            inventory_status,
            error_message,
            indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(relative_path) DO UPDATE SET
            original_path = excluded.original_path,
            filename = excluded.filename,
            extension = excluded.extension,
            file_size = excluded.file_size,
            width = excluded.width,
            height = excluded.height,
            image_format = excluded.image_format,
            modified_at = excluded.modified_at,
            modified_at_ns = excluded.modified_at_ns,
            captured_at = excluded.captured_at,
            sha256 = excluded.sha256,
            inventory_status = excluded.inventory_status,
            error_message = excluded.error_message,
            indexed_at = excluded.indexed_at
    """, (
        relative_path,
        original_path,
        filename,
        extension,
        file_size,
        width,
        height,
        image_format,
        modified_at,
        modified_at_ns,
        captured_at,
        sha256,
        status,
        error_message,
        datetime.now().isoformat(sep=" ", timespec="seconds")
    ))

    return status


# --------------------------------------------------
# INVENTORY
# --------------------------------------------------

def run_inventory(source: Path, database: Path, limit: int | None):
    if not source.exists() or not source.is_dir():
        raise SystemExit(f"Source folder does not exist: {source}")

    database.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")

    create_database(connection)

    print("\nScanning screenshot collection...")

    files = sorted(
        (
            path for path in source.rglob("*")
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: str(path).lower()
    )

    total_found = len(files)

    if limit is not None:
        files = files[:limit]

    total = len(files)

    print(f"Images discovered: {total_found:,}")
    print(f"Images to process: {total:,}")
    print(f"Database: {database}")
    print("\nStarting inventory...\n")

    success_count = 0
    error_count = 0
    start_time = time.time()

    try:
        for index, file_path in enumerate(files, start=1):
            try:
                status = process_image(
                    connection, file_path, source
                )

                if status == "ok":
                    success_count += 1
                else:
                    error_count += 1

                    logging.error(
                        "Image error: %s",
                        file_path
                    )

            except Exception as error:
                error_count += 1

                logging.exception(
                    "Failed to process %s",
                    file_path
                )

                print(f"\nERROR: {file_path.name}: {error}")

            # Save progress regularly
            if index % 100 == 0:
                connection.commit()

            if index % 10 == 0 or index == total:
                print(
                    f"\rProgress: {index:,}/{total:,} "
                    f"| Successful: {success_count:,} "
                    f"| Errors: {error_count:,}",
                    end="",
                    flush=True
                )

        connection.commit()

    finally:
        connection.close()

    elapsed = time.time() - start_time

    print("\n\nInventory completed.")
    print(f"Successful: {success_count:,}")
    print(f"Errors: {error_count:,}")
    print(f"Time taken: {elapsed:.2f} seconds")

    # Print duplicate summary from the database
    with sqlite3.connect(database) as connection:
        duplicate_groups, duplicate_files = connection.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(file_count), 0)
            FROM (
                SELECT COUNT(*) AS file_count
                FROM images
                WHERE sha256 IS NOT NULL
                GROUP BY sha256
                HAVING COUNT(*) > 1
            )
        """).fetchone()

        total_records = connection.execute(
            "SELECT COUNT(*) FROM images"
        ).fetchone()[0]

    print(f"Total database records: {total_records:,}")
    print(f"Duplicate hash groups: {duplicate_groups:,}")
    print(f"Files belonging to duplicate groups: {duplicate_files:,}")
    print("\nNo original files were modified or deleted.")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build a local screenshot inventory."
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Folder containing original screenshots"
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DATABASE,
        help="SQLite database location"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N images"
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")

    setup_logging()

    print("=" * 55)
    print("       SCREENSHOT KNOWLEDGE BASE")
    print("             IMAGE INVENTORY")
    print("=" * 55)

    run_inventory(
        args.source.resolve(),
        args.db.resolve(),
        args.limit
    )


if __name__ == "__main__":
    main()
