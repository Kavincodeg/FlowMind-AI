"""
FlowMind AI - Benchmark Startup Guard & In-Memory Retriever Tests

Tests:
  1. BenchmarkRunner startup fails when DEMO_MODE=true.
  2. BenchmarkRunner startup fails when retriever is mock or stub.
  3. BenchmarkRunner startup succeeds with DEMO_MODE=false and in_memory_retrieve.
  4. InMemoryRetriever dense semantic retrieval works with Phase 1 filters.
"""
from __future__ import annotations

import os
from unittest.mock import patch
import pytest

from backend.evaluation.runner import BenchmarkRunner
from backend.reasoning.llm_provider import MockLLMProvider
from backend.retrieval.in_memory_retriever import InMemoryRetriever, in_memory_retrieve
from backend.retrieval.mock_retriever import mock_retrieve
from backend.retrieval.models import MetadataFilter, RetrievalQuery


class TestBenchmarkStartupGuards:
    """Verify non-negotiable startup guards for the evaluation benchmark."""

    def test_startup_guard_blocks_demo_mode_true(self):
        """Evaluation benchmark must never run with DEMO_MODE=true."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            with pytest.raises(RuntimeError, match="Evaluation Startup Guard: DEMO_MODE is enabled"):
                BenchmarkRunner(
                    split="dev",
                    is_pilot=True,
                    runs=1,
                    llm_provider=MockLLMProvider(),
                    retriever_fn=in_memory_retrieve,
                )

    def test_startup_guard_blocks_mock_retriever(self):
        """Evaluation benchmark must fail if a mock or stub retriever is provided."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            with pytest.raises(RuntimeError, match="Evaluation Startup Guard: Mock or stub retriever detected"):
                BenchmarkRunner(
                    split="dev",
                    is_pilot=True,
                    runs=1,
                    llm_provider=MockLLMProvider(),
                    retriever_fn=mock_retrieve,
                )

    def test_startup_guard_passes_with_demo_mode_off_and_real_retriever(self):
        """Evaluation benchmark succeeds startup with DEMO_MODE=false and in_memory_retrieve."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            runner = BenchmarkRunner(
                split="dev",
                is_pilot=True,
                runs=1,
                llm_provider=MockLLMProvider(),
                retriever_fn=in_memory_retrieve,
            )
            assert runner.retriever_fn is in_memory_retrieve
            meta = runner.get_run_metadata()
            assert meta["retriever_type"] == "in_memory_retrieve"


class TestInMemoryRetrieverFunctionality:
    """Verify that InMemoryRetriever executes semantic search with Phase 1 metadata filters."""

    def test_in_memory_retriever_returns_results(self):
        q = RetrievalQuery(
            query_text="customer double charged duplicate billing refund",
            top_k=3,
            filters=MetadataFilter(source_type="ticket"),
            score_threshold=0.20,
        )
        res = in_memory_retrieve(q)
        assert res.total_found > 0
        assert len(res.chunks) <= 3
        for c in res.chunks:
            assert c.source_type == "ticket"
            assert c.score >= 0.20
            assert "Ticket" in c.citation

    def test_in_memory_retriever_policy_filter(self):
        q = RetrievalQuery(
            query_text="refund statutory warranty and approval threshold",
            top_k=3,
            filters=MetadataFilter(source_type="policy"),
            score_threshold=0.20,
        )
        res = in_memory_retrieve(q)
        assert res.total_found > 0
        for c in res.chunks:
            assert c.source_type == "policy"
            assert "Policy" in c.citation
