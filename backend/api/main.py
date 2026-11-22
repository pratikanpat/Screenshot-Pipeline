"""
backend/api/main.py
────────────────────
FastAPI application entry-point for the Screenshot Knowledge Base.

Start the server:
    uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

Then open:
    http://localhost:8000       → API info
    http://localhost:8000/docs  → Swagger UI
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import CHROMA_DIR, DATA_DIR, DATABASE
from backend.db.database import get_connection

from backend.api.routes import images, search, categories, process


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories + tables exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection(DATABASE)
    conn.close()
    yield
    # Shutdown: nothing to clean up


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Screenshot Knowledge Base",
    description=(
        "Search and browse your screenshot library. "
        "Keyword search via SQLite FTS5, semantic search via CLIP + ChromaDB, "
        "auto-categorisation via CLIP zero-shot and keyword rules."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(images.router)
app.include_router(search.router)
app.include_router(categories.router)
app.include_router(process.router)


# ─────────────────────────────────────────────────────────────────────────────
# Root
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["root"])
def root():
    return {
        "name": "Screenshot Knowledge Base API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "search":     "/search?q=<query>&mode=keyword|semantic|hybrid",
            "images":     "/images",
            "categories": "/categories",
            "status":     "/process/status",
            "start":      "POST /process/start",
        },
    }

