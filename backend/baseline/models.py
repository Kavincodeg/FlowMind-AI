"""
FlowMind AI - Plain-RAG Baseline Models (Phase 2)
Pydantic v2 data models for the comparison baseline (retrieve + answer only).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.retrieval.models import MetadataFilter


class BaselineQuery(BaseModel):
    """Input query to the plain-RAG baseline."""
    model_config = ConfigDict(extra="ignore")

    query_text: str
    top_k: int = Field(default=5, ge=1, le=20)
    filters: MetadataFilter = Field(default_factory=MetadataFilter)
    score_threshold: float = Field(default=0.25, ge=0.0, le=1.0)


class BaselineAnswer(BaseModel):
    """Output answer from the plain-RAG baseline. Retrieve and answer only, no action recommendation."""
    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    query_text: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    retrieved_chunks_count: int = 0
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    model_used: str = "mock"
