"""backend/api/routes/process.py — pipeline trigger and status endpoints."""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.api.models import ProcessStatus, ProcessStartRequest
from backend.config import DATABASE
from backend.db.database import get_connection
from backend.db.search import get_library_stats

router = APIRouter(prefix="/process", tags=["process"])

# Simple in-memory state (sufficient for a local tool)
_pipeline_state: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "current_stage": None,
    "started_at": None,
}


def _run_pipeline(source: str, steps: list[str], limit: int | None) -> None:
    """Blocking pipeline runner — called in a background thread."""
    from pathlib import Path
    from backend.pipeline.ingestion import run_ingestion
    from backend.pipeline.ocr import run_ocr
    from backend.pipeline.classifier import run_classification
    from backend.pipeline.embeddings import run_embeddings

    _pipeline_state["running"] = True
    _pipeline_state["started_at"] = datetime.now().isoformat()

    conn = get_connection(DATABASE)
    try:
        if "ingest" in steps:
            _pipeline_state["current_stage"] = "ingest"
            run_ingestion(Path(source), limit, conn)

        stats = get_library_stats(conn)
        _pipeline_state["total"] = stats["total"]

        if "ocr" in steps:
            _pipeline_state["current_stage"] = "ocr"
            run_ocr(conn, limit=limit)

        if "classify" in steps:
            _pipeline_state["current_stage"] = "classify"
            run_classification(conn, limit=limit)

        if "embed" in steps:
            _pipeline_state["current_stage"] = "embed"
            run_embeddings(conn, limit=limit)

    finally:
        conn.close()
        _pipeline_state["running"] = False
        _pipeline_state["current_stage"] = None


@router.get("/status", response_model=ProcessStatus)
def pipeline_status():
    """Return current pipeline state and image counts."""
    conn = get_connection(DATABASE)
    stats = get_library_stats(conn)
    conn.close()

    return ProcessStatus(
        running=_pipeline_state["running"],
        total=stats["total"],
        done=stats["processed"],
        remaining=stats["pending"],
        current_stage=_pipeline_state.get("current_stage"),
    )


@router.post("/start")
def start_pipeline(request: ProcessStartRequest):
    """
    Start the pipeline in a background thread.
    Returns immediately — poll /process/status for progress.
    """
    if _pipeline_state["running"]:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Poll /process/status.",
        )

    thread = threading.Thread(
        target=_run_pipeline,
        args=(request.source, request.steps, request.limit),
        daemon=True,
    )
    thread.start()

    return {
        "message": "Pipeline started.",
        "source": request.source,
        "steps": request.steps,
        "poll": "/process/status",
    }
