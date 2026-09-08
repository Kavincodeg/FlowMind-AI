"""
FlowMind AI - Plain-RAG Baseline Tests (Phase 2)
Tests for the comparison baseline: retrieve and answer only,
without recommendation, approval, or execution logic.
"""
from __future__ import annotations

import uuid
import pytest

from backend.baseline.models import BaselineAnswer, BaselineQuery
from backend.baseline.service import PlainRAGBaseline, answer_baseline_query
from backend.reasoning.llm_provider import MockLLMProvider
from backend.retrieval.models import (
    MetadataFilter,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
)


def make_dummy_chunk(source_type: str, source_id: str, content: str = "Evidence content") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        doc_id=uuid.uuid4(),
        source_type=source_type,
        source_id=source_id,
        chunk_index=0,
        content=content,
        score=0.85,
        metadata={"source_type": source_type, "source_id": source_id},
    )


class TestPlainRAGBaseline:
    def test_baseline_returns_answer_with_citations(self):
        def dummy_retriever(q: RetrievalQuery) -> RetrievalResult:
            chunks = [
                make_dummy_chunk("ticket", "TKT-0033", "Customer reports damaged goods."),
                make_dummy_chunk("policy", "escalation_policy.md", "Repeat contact policy."),
            ]
            return RetrievalResult(
                query_text=q.query_text,
                chunks=chunks,
                total_found=len(chunks),
                filters_applied={},
                retrieval_time_ms=10.0,
            )

        baseline = PlainRAGBaseline(retriever_fn=dummy_retriever, llm_provider=MockLLMProvider())
        query = BaselineQuery(query_text="What are the repeat contact rules?")
        result = baseline.answer(query)

        assert isinstance(result, BaselineAnswer)
        assert result.query_text == "What are the repeat contact rules?"
        assert len(result.answer) > 0
        assert len(result.citations) == 2
        assert "[Ticket TKT-0033, chunk 0]" in result.citations
        assert "[Policy: escalation_policy.md, chunk 0]" in result.citations
        assert result.retrieved_chunks_count == 2
        assert result.retrieval_time_ms > 0

        # Non-negotiable structural check: Baseline must NOT have recommendation or approval attributes
        assert not hasattr(result, "recommendation")
        assert not hasattr(result, "requires_approval")
        assert not hasattr(result, "action_type")

    def test_baseline_empty_retrieval_response(self):
        def empty_retriever(q: RetrievalQuery) -> RetrievalResult:
            return RetrievalResult(
                query_text=q.query_text,
                chunks=[],
                total_found=0,
                filters_applied={},
                retrieval_time_ms=5.0,
            )

        baseline = PlainRAGBaseline(retriever_fn=empty_retriever, llm_provider=MockLLMProvider())
        query = BaselineQuery(query_text="Non-existent query with zero matches")
        result = baseline.answer(query)

        assert result.retrieved_chunks_count == 0
        assert result.citations == []
        assert "could not find any relevant information" in result.answer.lower()

    def test_answer_baseline_query_convenience_function(self):
        def dummy_retriever(q: RetrievalQuery) -> RetrievalResult:
            chunks = [make_dummy_chunk("policy", "sla_policy.md", "SLA policy text")]
            return RetrievalResult(
                query_text=q.query_text,
                chunks=chunks,
                total_found=1,
                filters_applied={},
                retrieval_time_ms=8.0,
            )

        query = BaselineQuery(query_text="What is the high priority SLA?")
        result = answer_baseline_query(query, retriever_fn=dummy_retriever, llm_provider=MockLLMProvider())
        assert isinstance(result, BaselineAnswer)
        assert len(result.citations) == 1
