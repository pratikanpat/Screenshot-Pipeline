
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import Output


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE = PROJECT_ROOT / "data" / "library.db"
LOG_FILE = PROJECT_ROOT / "data" / "logs" / "ocr.log"

TESSERACT_CONFIG = "--oem 3 --psm 6"

# Languages installed in your Tesseract installation
ENGLISH = "eng"
DEVANAGARI_LANGUAGES = ["hin", "mar"]

ENGINE_NAME = "tesseract"
ENGINE_VERSION = str(pytesseract.get_tesseract_version())


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

def create_tables(connection):

    connection.execute("""
        CREATE TABLE IF NOT EXISTS ocr_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL UNIQUE,
            extracted_text TEXT,
            detected_script TEXT,
            selected_language TEXT,
            confidence REAL,
            processing_time REAL,
            engine_name TEXT,
            engine_version TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            processed_at TEXT,

            FOREIGN KEY(image_id)
                REFERENCES images(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS ocr_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            extracted_text TEXT,
            confidence REAL,
            word_count INTEGER,
            engine_version TEXT,
            created_at TEXT,

            UNIQUE(image_id, language, engine_version),

            FOREIGN KEY(image_id)
                REFERENCES images(id)
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_ocr_results_status
        ON ocr_results(status)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_ocr_candidates_image
        ON ocr_candidates(image_id)
    """)

    connection.commit()


# --------------------------------------------------
# OCR TEXT EXTRACTION
# --------------------------------------------------

def extract_text(image, language):

    data = pytesseract.image_to_data(
        image,
        lang=language,
        config=TESSERACT_CONFIG,
        output_type=Output.DICT
    )

    words = []
    confidence_values = []

    for index, word in enumerate(data["text"]):

        word = word.strip()

        if not word:
            continue

        try:
            confidence = float(data["conf"][index])
        except (ValueError, TypeError):
            continue

        if confidence >= 0:
            words.append(word)
            confidence_values.append(confidence)

    extracted_text = " ".join(words)

    average_confidence = (
        sum(confidence_values) / len(confidence_values)
        if confidence_values else None
    )

    return {
        "text": extracted_text,
        "confidence": average_confidence,
        "word_count": len(words)
    }


# --------------------------------------------------
# SCRIPT DETECTION
# --------------------------------------------------

def detect_script(image):

    """
    Tesseract OSD attempts to identify the writing script.

    It is a signal, not a guaranteed language classifier.
    """

    try:
        result = pytesseract.image_to_osd(
            image,
            lang="osd",
            config="--psm 0"
        )

        match = re.search(
            r"Script:\s*(.+)",
            result
        )

        if match:
            return match.group(1).strip()

    except pytesseract.TesseractError:
        logging.info("OSD could not detect script for an image.")

    except Exception:
        logging.exception("Unexpected script detection error.")

    return "Unknown"


# --------------------------------------------------
# CANDIDATE STORAGE
# --------------------------------------------------

def save_candidate(
    connection,
    image_id,
    language,
    result
):

    connection.execute("""
        INSERT INTO ocr_candidates (
            image_id,
            language,
            extracted_text,
            confidence,
            word_count,
            engine_version,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(image_id, language, engine_version)
        DO UPDATE SET
            extracted_text = excluded.extracted_text,
            confidence = excluded.confidence,
            word_count = excluded.word_count,
            created_at = excluded.created_at
    """, (
        image_id,
        language,
        result["text"],
        result["confidence"],
        result["word_count"],
        ENGINE_VERSION,
        datetime.now().isoformat(sep=" ")
    ))


# --------------------------------------------------
# PROCESS ONE IMAGE
# --------------------------------------------------

def process_image(connection, image_id, image_path):

    start_time = time.perf_counter()

    try:

        with Image.open(image_path) as original:
            image = original.convert("RGB")

        # 1. Always run English OCR
        english_result = extract_text(image, ENGLISH)

        save_candidate(
            connection,
            image_id,
            ENGLISH,
            english_result
        )

        # 2. Detect the script
        detected_script = detect_script(image)

        candidates = [english_result]
        selected_language = ENGLISH

        # 3. Run Hindi and Marathi only for
        #    images identified as Devanagari
        if detected_script.lower() == "devanagari":

            for language in DEVANAGARI_LANGUAGES:

                result = extract_text(image, language)

                save_candidate(
                    connection,
                    image_id,
                    language,
                    result
                )

                candidates.append(result)

            # Select the candidate with the highest
            # Tesseract confidence as a provisional default.
            # All candidates remain stored separately.
            devanagari_candidates = candidates[1:]

            valid_candidates = [
                candidate
                for candidate in devanagari_candidates
                if candidate["confidence"] is not None
                and candidate["text"].strip()
            ]

            if valid_candidates:
                selected = max(
                    valid_candidates,
                    key=lambda item: item["confidence"]
                )

                selected_language = (
                    DEVANAGARI_LANGUAGES[
                        devanagari_candidates.index(selected)
                    ]
                )

                selected_text = selected["text"]
                selected_confidence = selected["confidence"]

            else:
                selected_text = english_result["text"]
                selected_confidence = english_result["confidence"]

        else:
            selected_text = english_result["text"]
            selected_confidence = english_result["confidence"]

        processing_time = time.perf_counter() - start_time

        # 4. Save final OCR result
        connection.execute("""
            INSERT INTO ocr_results (
                image_id,
                extracted_text,
                detected_script,
                selected_language,
                confidence,
                processing_time,
                engine_name,
                engine_version,
                status,
                error_message,
                processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(image_id) DO UPDATE SET
                extracted_text = excluded.extracted_text,
                detected_script = excluded.detected_script,
                selected_language = excluded.selected_language,
                confidence = excluded.confidence,
                processing_time = excluded.processing_time,
                engine_name = excluded.engine_name,
                engine_version = excluded.engine_version,
                status = excluded.status,
                error_message = excluded.error_message,
                processed_at = excluded.processed_at
        """, (
            image_id,
            selected_text,
            detected_script,
            selected_language,
            selected_confidence,
            processing_time,
            ENGINE_NAME,
            ENGINE_VERSION,
            "success",
            None,
            datetime.now().isoformat(sep=" ")
        ))

        return "success"

    except (
        OSError,
        UnidentifiedImageError,
        pytesseract.TesseractError
    ) as error:

        processing_time = time.perf_counter() - start_time

        connection.execute("""
            INSERT INTO ocr_results (
                image_id,
                processing_time,
                engine_name,
                engine_version,
                status,
                error_message,
                processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(image_id) DO UPDATE SET
                processing_time = excluded.processing_time,
                engine_name = excluded.engine_name,
                engine_version = excluded.engine_version,
                status = excluded.status,
                error_message = excluded.error_message,
                processed_at = excluded.processed_at
        """, (
            image_id,
            processing_time,
            ENGINE_NAME,
            ENGINE_VERSION,
            "failed",
            str(error),
            datetime.now().isoformat(sep=" ")
        ))

        logging.error(
            "OCR failed for image ID %s: %s",
            image_id,
            error
        )

        return "failed"

    except Exception as error:

        logging.exception(
            "Unexpected OCR error for image ID %s",
            image_id
        )

        connection.execute("""
            INSERT INTO ocr_results (
                image_id,
                engine_name,
                engine_version,
                status,
                error_message,
                processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(image_id) DO UPDATE SET
                status = excluded.status,
                error_message = excluded.error_message,
                processed_at = excluded.processed_at
        """, (
            image_id,
            ENGINE_NAME,
            ENGINE_VERSION,
            "failed",
            str(error),
            datetime.now().isoformat(sep=" ")
        ))

        return "failed"


# --------------------------------------------------
# MAIN PROCESSING QUEUE
# --------------------------------------------------

def run_ocr(limit=None, force=False, retry_failed=False):

    if not DATABASE.exists():
        raise SystemExit(
            "Inventory database not found. Run inventory.py first."
        )

    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")

    create_tables(connection)

    # Select images that need processing.
    # Previously successful images are skipped by default.
    query = """
        SELECT i.id, i.original_path
        FROM images i
        LEFT JOIN ocr_results o ON i.id = o.image_id
        WHERE i.inventory_status = 'ok'
    """

    if force:
        pass

    elif retry_failed:
        query += """
            AND (
                o.image_id IS NULL
                OR o.status != 'success'
            )
        """

    else:
        query += """
            AND o.image_id IS NULL
        """

    query += " ORDER BY i.relative_path"

    if limit is not None:
        query += " LIMIT ?"
        rows = connection.execute(query, (limit,)).fetchall()
    else:
        rows = connection.execute(query).fetchall()

    total = len(rows)

    print(f"\nImages queued for OCR: {total:,}")
    print(f"Tesseract version: {ENGINE_VERSION}")
    print("\nStarting OCR...\n")

    success_count = 0
    failure_count = 0

    start_time = time.perf_counter()

    try:

        for index, (image_id, image_path) in enumerate(
            rows, start=1
        ):

            status = process_image(
                connection,
                image_id,
                Path(image_path)
            )

            if status == "success":
                success_count += 1
            else:
                failure_count += 1

            # Commit regularly so progress survives interruptions.
            if index % 10 == 0:
                connection.commit()

            if index % 5 == 0 or index == total:
                print(
                    f"\rProgress: {index:,}/{total:,} "
                    f"| Successful: {success_count:,} "
                    f"| Failed: {failure_count:,}",
                    end="",
                    flush=True
                )

        connection.commit()

    finally:
        connection.close()

    elapsed = time.perf_counter() - start_time

    print("\n\nOCR processing completed.")
    print(f"Successful: {success_count:,}")
    print(f"Failed: {failure_count:,}")
    print(f"Time taken: {elapsed:.2f} seconds")

    print("\nPreviously processed images are preserved.")
    print("OCR results are stored in data/library.db.")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Resumable screenshot OCR engine."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only N pending images."
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all eligible images."
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry failed images and process pending ones."
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")

    if args.force and args.retry_failed:
        parser.error(
            "Use either --force or --retry-failed, not both."
        )

    setup_logging()

    print("=" * 55)
    print("       SCREENSHOT KNOWLEDGE BASE")
    print("               OCR ENGINE")
    print("=" * 55)

    run_ocr(
        limit=args.limit,
        force=args.force,
        retry_failed=args.retry_failed
    )


if __name__ == "__main__":
    main()
