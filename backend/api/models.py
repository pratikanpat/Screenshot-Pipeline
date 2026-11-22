"""
backend/api/models.py
──────────────────────
Pydantic v2 response schemas for the FastAPI layer.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Image models
# ─────────────────────────────────────────────────────────────────────────────

class ImageBase(BaseModel):
    id: int
    filename: str
    original_path: str
    width: int | None = None
    height: int | None = None
    captured_at: str | None = None
    status: str


class ImageDetail(ImageBase):
    modified_at: str | None = None
    file_size: int | None = None
    sha256: str | None = None
    # OCR
    extracted_text: str | None = None
    language: str | None = None
    ocr_confidence: float | None = None
    engine: str | None = None
    word_count: int | None = None
    # Category
    category: str | None = None
    subcategory: str | None = None
    content_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    cat_confidence: float | None = None
    method: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Search models
# ─────────────────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    image_id: int
    filename: str
    original_path: str
    width: int | None = None
    height: int | None = None
    captured_at: str | None = None
    category: str | None = None
    subcategory: str | None = None
    content_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    snippet: str = ""
    score: float = 0.0
    search_mode: str = "keyword"


class SearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    results: list[SearchResult]
    time_ms: float


# ─────────────────────────────────────────────────────────────────────────────
# Category / library models
# ─────────────────────────────────────────────────────────────────────────────

class SubcategoryInfo(BaseModel):
    name: str
    count: int


class CategoryInfo(BaseModel):
    name: str
    subcategories: list[SubcategoryInfo] = Field(default_factory=list)
    count: int = 0


class LibraryStats(BaseModel):
    total_images: int
    processed: int
    pending: int
    failed: int
    categories: list[CategoryInfo] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Process status model
# ─────────────────────────────────────────────────────────────────────────────

class ProcessStatus(BaseModel):
    running: bool = False
    total: int = 0
    done: int = 0
    remaining: int = 0
    eta_seconds: float | None = None
    current_stage: str | None = None


class ProcessStartRequest(BaseModel):
    source: str
    steps: list[str] = Field(
        default=["ingest", "ocr", "classify", "embed"],
        description="Pipeline stages to run.",
    )
    limit: int | None = None
