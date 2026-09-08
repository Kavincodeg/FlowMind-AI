"""
FlowMind AI - Retriever (Phase 1)

Top-level retrieval interface:
  - Accepts a RetrievalQuery (text + optional filters + top_k + threshold)
  - Embeds the query
  - Builds a metadata filter dict for pgvector containment search
  - Calls store.ann_search
  - Returns a RetrievalResult with cited chunks

This is the ONLY entry point that the reasoning layer (Phase 2) will call.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from backend.retrieval.embedder import get_embedder
from backend.retrieval.models import MetadataFilter, RetrievalQuery, RetrievalResult
from backend.retrieval.store import ann_search

logger = logging.getLogger(__name__)


def retrieve(query: RetrievalQuery) -> RetrievalResult:
    """
    Execute a retrieval query and return ranked, cited chunks.

    Args:
        query: RetrievalQuery with text, top_k, filters, and score_threshold

    Returns:
        RetrievalResult containing matched chunks with citations
    """
    t0 = time.perf_counter()

    # 1. Embed the query
    embedder = get_embedder()
    query_vec = embedder.embed_query(query.query_text)

    # 2. Build metadata filter dict for pgvector @> containment
    filter_dict = _build_filter(query.filters)

    # 3. ANN search
    try:
        chunks = ann_search(
            query_vector=query_vec,
            top_k=query.top_k,
            metadata_filter=filter_dict if filter_dict else None,
            score_threshold=query.score_threshold,
        )
    except Exception as exc:
        logger.warning(
            "Vector database unavailable (%s); falling back to mock_retrieve for offline operation.",
            exc,
        )
        from backend.retrieval.mock_retriever import mock_retrieve
        return mock_retrieve(query)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "Retrieved %d chunks for query=%r in %.1f ms",
        len(chunks), query.query_text[:60], elapsed_ms,
    )

    return RetrievalResult(
        query_text=query.query_text,
        chunks=chunks,
        total_found=len(chunks),
        filters_applied=filter_dict,
        retrieval_time_ms=round(elapsed_ms, 2),
    )


# ------------------------------------------------------------------
# Filter builder
# ------------------------------------------------------------------

def _build_filter(f: MetadataFilter) -> Dict[str, Any]:
    """
    Convert a MetadataFilter into a JSONB containment dict.

    Only non-None fields are included.
    Date range filters are handled separately in store.py via SQL.
    """
    d: Dict[str, Any] = {}

    if f.source_type is not None:
        d["source_type"] = f.source_type
    if f.issue_category is not None:
        d["issue_category"] = f.issue_category
    if f.status is not None:
        d["status"] = f.status
    if f.priority is not None:
        d["priority"] = f.priority
    if f.assigned_team is not None:
        d["assigned_team"] = f.assigned_team
    if f.sla_breach is not None:
        d["sla_breach"] = f.sla_breach

    return d


# ------------------------------------------------------------------
# Convenience shorthand
# ------------------------------------------------------------------

def quick_retrieve(
    query_text: str,
    top_k: int = 5,
    source_type: Optional[str] = None,
    issue_category: Optional[str] = None,
    priority: Optional[str] = None,
    score_threshold: float = 0.30,
) -> RetrievalResult:
    """
    Convenience wrapper for the most common retrieval patterns.

    Example:
        result = quick_retrieve("billing dispute refund request", top_k=5,
                                source_type="ticket", priority="high")
        print(result.combined_context)
    """
    filters = MetadataFilter(
        source_type=source_type,
        issue_category=issue_category,
        priority=priority,
    )
    q = RetrievalQuery(
        query_text=query_text,
        top_k=top_k,
        filters=filters,
        score_threshold=score_threshold,
    )
    return retrieve(q)
