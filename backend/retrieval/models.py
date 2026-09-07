"""
FlowMind AI - Retrieval Layer Data Models (Phase 1)
Pydantic v2 models for documents, chunks, and retrieval results.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Document metadata
# ============================================================

class DocumentMetadata(BaseModel):
    """Flexible metadata attached to a source document."""
    model_config = ConfigDict(extra="allow")

    source_type: str               # 'ticket' | 'policy'
    source_id: str

    # Ticket fields
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    issue_category: Optional[str] = None
    status: Optional[str] = None           # open | escalated | resolved
    assigned_team: Optional[str] = None
    priority: Optional[str] = None         # low | medium | high
    sla_breach: Optional[bool] = None
    ticket_created_at: Optional[datetime] = None
    ticket_updated_at: Optional[datetime] = None

    # Policy fields
    filename: Optional[str] = None
    policy_category: Optional[str] = None


class Document(BaseModel):
    """One ingested source document (pre-chunking)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    doc_id: Optional[UUID] = None
    source_type: str
    source_id: str
    title: str
    content: str
    metadata: DocumentMetadata


# ============================================================
# Chunks
# ============================================================

class Chunk(BaseModel):
    """One text chunk ready to be embedded and stored."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    chunk_id: Optional[UUID] = None
    doc_id: Optional[UUID] = None
    chunk_index: int
    content: str
    token_count: Optional[int] = None
    char_offset: Optional[int] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Retrieval
# ============================================================

class MetadataFilter(BaseModel):
    """Optional filters to narrow the vector search."""
    source_type: Optional[str] = None
    issue_category: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_team: Optional[str] = None
    sla_breach: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class RetrievalQuery(BaseModel):
    """Input to the retriever."""
    query_text: str
    top_k: int = Field(default=5, ge=1, le=50)
    filters: MetadataFilter = Field(default_factory=MetadataFilter)
    score_threshold: float = Field(default=0.30, ge=0.0, le=1.0)


class RetrievedChunk(BaseModel):
    """One retrieved chunk with citation information."""
    chunk_id: UUID
    doc_id: UUID
    source_type: str
    source_id: str
    chunk_index: int
    content: str
    score: float
    metadata: Dict[str, Any]

    @property
    def citation(self) -> str:
        if self.source_type == "ticket":
            return f"[Ticket {self.source_id}, chunk {self.chunk_index}]"
        return f"[Policy: {self.source_id}, chunk {self.chunk_index}]"


class RetrievalResult(BaseModel):
    """Full result from the retriever."""
    query_text: str
    chunks: List[RetrievedChunk]
    total_found: int
    filters_applied: Dict[str, Any]
    retrieval_time_ms: float

    @property
    def citations(self) -> List[str]:
        return [c.citation for c in self.chunks]

    @property
    def combined_context(self) -> str:
        """Concatenated chunk text with citation headers, ready for LLM."""
        parts = []
        for c in self.chunks:
            parts.append(
                f"--- {c.citation} (score: {c.score:.3f}) ---\n{c.content}"
            )
        return "\n\n".join(parts)
