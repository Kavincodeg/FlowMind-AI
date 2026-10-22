"""
FlowMind AI - In-Memory MiniLM Retriever (Phase 1 / Evaluation)

Provides high-performance, in-memory semantic retrieval using SentenceTransformers
all-MiniLM-L6-v2 embeddings + cosine similarity over the full chunk store
(all tickets + all policy chunks).

Features:
  - Exact Phase 1 chunking via load_tickets() and load_policies()
  - Full corpus indexing (150 ticket chunks + 37 policy chunks = 187 chunks)
  - Dense vector representations (384-dimensional normalized float32 embeddings)
  - Numpy cosine similarity dot product
  - Phase 1 metadata filtering (source_type, issue_category, priority, status, assigned_team, sla_breach)
  - Score threshold enforcement
  - Real RetrievedChunk instances with citations
  - Zero keyword matching or hardcoded query-to-chunk maps
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from backend.retrieval.embedder import get_embedder, Embedder
from backend.retrieval.ingestion import load_tickets, load_policies
from backend.retrieval.models import (
    Chunk,
    Document,
    MetadataFilter,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)

# Root and data directory anchors
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_TICKETS_PATH = _DEFAULT_ROOT / "backend" / "data" / "synthetic" / "tickets.json"
_DEFAULT_POLICIES_DIR = _DEFAULT_ROOT / "backend" / "data" / "policies"


class InMemoryRetriever:
    """
    In-memory dense retriever evaluating semantic similarity via all-MiniLM-L6-v2 embeddings.
    """

    def __init__(
        self,
        tickets_path: Optional[Path] = None,
        policies_dir: Optional[Path] = None,
        embedder: Optional[Embedder] = None,
    ):
        self.tickets_path = tickets_path or _DEFAULT_TICKETS_PATH
        self.policies_dir = policies_dir or _DEFAULT_POLICIES_DIR
        self.embedder = embedder or get_embedder()
        self._chunks: List[Chunk] = []
        self._embeddings: Optional[np.ndarray] = None
        self._indexed = False
        self._build_index()

    def _build_index(self) -> None:
        """Load corpus and compute dense embeddings for all chunks."""
        t0 = time.perf_counter()
        logger.info("Initializing InMemoryRetriever from %s and %s...", self.tickets_path, self.policies_dir)

        # 1. Load tickets
        docs_t, chunks_t = load_tickets(self.tickets_path)
        for c in chunks_t:
            if "source_type" not in c.metadata:
                c.metadata["source_type"] = "ticket"

        # 2. Load policies
        docs_p, chunks_p = load_policies(self.policies_dir)
        for c in chunks_p:
            if "source_type" not in c.metadata:
                c.metadata["source_type"] = "policy"

        self._chunks = chunks_t + chunks_p
        texts = [c.content for c in self._chunks]

        # 3. Batch embed texts
        self._embeddings = self.embedder.embed_texts(texts)
        self._indexed = True
        elapsed_s = time.perf_counter() - t0
        logger.info(
            "InMemoryRetriever indexed %d chunks (%d tickets, %d policies) in %.2fs",
            len(self._chunks), len(chunks_t), len(chunks_p), elapsed_s,
        )

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """
        Execute dense vector retrieval over indexed chunks with metadata filtering.
        """
        if not self._indexed or self._embeddings is None:
            raise RuntimeError("InMemoryRetriever is not indexed.")

        t0 = time.perf_counter()

        # 1. Embed query
        query_vec = self.embedder.embed_query(query.query_text)

        # 2. Apply metadata filter matching Phase 1 _build_filter logic
        filter_dict: Dict[str, Any] = {}
        candidate_indices: List[int] = []

        f = query.filters
        if f:
            if f.source_type is not None:
                filter_dict["source_type"] = f.source_type
            if f.issue_category is not None:
                filter_dict["issue_category"] = f.issue_category
            if f.status is not None:
                filter_dict["status"] = f.status
            if f.priority is not None:
                filter_dict["priority"] = f.priority
            if f.assigned_team is not None:
                filter_dict["assigned_team"] = f.assigned_team
            if f.sla_breach is not None:
                filter_dict["sla_breach"] = f.sla_breach

        for idx, chunk in enumerate(self._chunks):
            meta = chunk.metadata
            match = True
            for k, expected_v in filter_dict.items():
                actual_v = meta.get(k)
                if actual_v != expected_v:
                    match = False
                    break
            if match:
                candidate_indices.append(idx)

        # If no candidates match metadata filter
        if not candidate_indices:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return RetrievalResult(
                query_text=query.query_text,
                chunks=[],
                total_found=0,
                filters_applied=filter_dict,
                retrieval_time_ms=round(elapsed_ms, 2),
            )

        # 3. Dense Cosine Similarity via dot product
        cand_embeddings = self._embeddings[candidate_indices]
        similarities = cand_embeddings @ query_vec

        # 4. Sort and filter by threshold
        ranked_order = np.argsort(-similarities)

        results: List[RetrievedChunk] = []
        for r_idx in ranked_order:
            score = float(similarities[r_idx])
            if score < query.score_threshold:
                continue

            orig_idx = candidate_indices[r_idx]
            chunk = self._chunks[orig_idx]
            meta = dict(chunk.metadata)
            stype = meta.get("source_type", "ticket")
            sid = meta.get("source_id", "")

            # Generate deterministic UUIDs from source identity
            doc_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{stype}:{sid}")
            chunk_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{stype}:{sid}:{chunk.chunk_index}")

            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    source_type=stype,
                    source_id=sid,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    score=round(score, 4),
                    metadata=meta,
                )
            )
            if len(results) >= query.top_k:
                break

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return RetrievalResult(
            query_text=query.query_text,
            chunks=results,
            total_found=len(results),
            filters_applied=filter_dict,
            retrieval_time_ms=round(elapsed_ms, 2),
        )


# Global singleton instance
_in_memory_retriever: Optional[InMemoryRetriever] = None


def get_in_memory_retriever() -> InMemoryRetriever:
    """Get or initialize the in-memory retriever singleton."""
    global _in_memory_retriever
    if _in_memory_retriever is None:
        _in_memory_retriever = InMemoryRetriever()
    return _in_memory_retriever


def in_memory_retrieve(query: RetrievalQuery) -> RetrievalResult:
    """Functional retrieval interface for InMemoryRetriever."""
    return get_in_memory_retriever().retrieve(query)
