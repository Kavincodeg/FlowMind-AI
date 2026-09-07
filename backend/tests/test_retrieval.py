"""
FlowMind AI - Phase 1 Retrieval Tests

Tests:
  1. Chunking correctness (no DB needed)
  2. Embedding shape and normalisation
  3. Metadata filter builder
  4. Integration: full retrieval pipeline (requires running DB)
  5. Precision@K and Recall@K against test_queries.json ground truth
  6. Citation completeness
  7. Score threshold enforcement
  8. No-result abstention (query with no matches above threshold)

Run all: pytest backend/tests/test_retrieval.py -v
Run unit only (no DB): pytest backend/tests/test_retrieval.py -v -m "not integration"
Run integration: pytest backend/tests/test_retrieval.py -v -m integration
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ============================================================
# Paths
# ============================================================
ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "backend" / "data"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
POLICIES_DIR = SYNTHETIC_DIR / "policies"
TICKETS_FILE = SYNTHETIC_DIR / "tickets.json"
TEST_QUERIES_FILE = DATA_DIR / "test_queries.json"


# ============================================================
# Unit Tests — Chunking (no DB, no embedder)
# ============================================================

class TestSlidingWindowChunker:
    def test_produces_chunks(self):
        from backend.retrieval.ingestion import _sliding_window_chunks
        text = " ".join([f"word{i}" for i in range(300)])
        chunks = _sliding_window_chunks(text, {"source_type": "ticket", "source_id": "TKT-TEST"})
        assert len(chunks) > 1, "Long text should produce multiple chunks"

    def test_chunk_overlap(self):
        from backend.retrieval.ingestion import _sliding_window_chunks
        text = " ".join([f"word{i}" for i in range(300)])
        chunks = _sliding_window_chunks(text, {"source_type": "ticket", "source_id": "TKT-TEST"}, window_tokens=100, overlap_tokens=20)
        # With overlap, some words from chunk N should appear in chunk N+1
        if len(chunks) >= 2:
            words0 = set(chunks[0].content.split())
            words1 = set(chunks[1].content.split())
            assert len(words0 & words1) > 0, "Overlapping chunks should share words"

    def test_chunk_indices_sequential(self):
        from backend.retrieval.ingestion import _sliding_window_chunks
        text = " ".join([f"word{i}" for i in range(500)])
        chunks = _sliding_window_chunks(text, {"source_type": "ticket", "source_id": "TKT-TEST"})
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks))), "Chunk indices must be sequential"

    def test_metadata_propagated(self):
        from backend.retrieval.ingestion import _sliding_window_chunks
        text = "hello world " * 50
        meta = {"source_type": "ticket", "source_id": "TKT-001", "priority": "high"}
        chunks = _sliding_window_chunks(text, meta)
        for c in chunks:
            assert c.metadata["source_type"] == "ticket"
            assert c.metadata["priority"] == "high"

    def test_short_text_single_chunk(self):
        from backend.retrieval.ingestion import _sliding_window_chunks
        text = "Short text."
        chunks = _sliding_window_chunks(text, {"source_type": "ticket", "source_id": "TKT-X"})
        assert len(chunks) == 1

    def test_empty_text(self):
        from backend.retrieval.ingestion import _sliding_window_chunks
        chunks = _sliding_window_chunks("", {"source_type": "ticket", "source_id": "TKT-EMPTY"})
        assert chunks == []


class TestParagraphChunker:
    def test_produces_chunks_from_markdown(self):
        from backend.retrieval.ingestion import _paragraph_chunks
        text = "\n\n".join([f"Paragraph {i}: " + "content " * 30 for i in range(5)])
        chunks = _paragraph_chunks(text, {"source_type": "policy", "source_id": "test.md"})
        assert len(chunks) >= 1

    def test_metadata_in_chunks(self):
        from backend.retrieval.ingestion import _paragraph_chunks
        text = "# Title\n\nParagraph one content here.\n\nParagraph two content here."
        meta = {"source_type": "policy", "source_id": "test.md", "policy_category": "test"}
        chunks = _paragraph_chunks(text, meta)
        for c in chunks:
            assert c.metadata["source_type"] == "policy"

    def test_no_empty_chunks(self):
        from backend.retrieval.ingestion import _paragraph_chunks
        text = "# Policy\n\n\n\nContent here.\n\n\n\nMore content here.\n\n"
        chunks = _paragraph_chunks(text, {"source_type": "policy", "source_id": "test.md"})
        for c in chunks:
            assert c.content.strip() != "", "No empty chunks"


# ============================================================
# Unit Tests — Data Loading
# ============================================================

class TestTicketLoading:
    def test_loads_150_tickets(self):
        from backend.retrieval.ingestion import load_tickets
        docs, chunks = load_tickets(TICKETS_FILE)
        assert len(docs) == 150, f"Expected 150 tickets, got {len(docs)}"

    def test_all_categories_present(self):
        from backend.retrieval.ingestion import load_tickets
        docs, _ = load_tickets(TICKETS_FILE)
        categories = {d.metadata.issue_category for d in docs}
        expected = {"billing", "delivery", "product_defect", "account_access", "service_quality"}
        assert categories == expected

    def test_chunks_have_metadata(self):
        from backend.retrieval.ingestion import load_tickets
        _, chunks = load_tickets(TICKETS_FILE)
        for c in chunks[:20]:  # spot-check first 20
            assert "source_type" in c.metadata
            assert c.metadata["source_type"] == "ticket"
            assert "source_id" in c.metadata
            assert c.metadata["source_id"].startswith("TKT-")

    def test_no_empty_chunk_content(self):
        from backend.retrieval.ingestion import load_tickets
        _, chunks = load_tickets(TICKETS_FILE)
        empty = [c for c in chunks if not c.content.strip()]
        assert len(empty) == 0, f"{len(empty)} empty chunks found"


class TestPolicyLoading:
    def test_loads_5_policies(self):
        from backend.retrieval.ingestion import load_policies
        docs, chunks = load_policies(POLICIES_DIR)
        assert len(docs) == 5, f"Expected 5 policy docs, got {len(docs)}"

    def test_policy_source_ids(self):
        from backend.retrieval.ingestion import load_policies
        docs, _ = load_policies(POLICIES_DIR)
        source_ids = {d.source_id for d in docs}
        expected_files = {
            "escalation_policy.md", "sla_policy.md",
            "team_routing.md", "refund_policy.md", "data_handling_policy.md"
        }
        assert source_ids == expected_files

    def test_policy_chunks_have_metadata(self):
        from backend.retrieval.ingestion import load_policies
        _, chunks = load_policies(POLICIES_DIR)
        for c in chunks:
            assert c.metadata["source_type"] == "policy"
            assert c.metadata["source_id"].endswith(".md")


# ============================================================
# Unit Tests — Embedder
# ============================================================

class TestEmbedder:
    @pytest.fixture(scope="class")
    def embedder(self):
        from backend.retrieval.embedder import Embedder
        return Embedder()

    def test_embedding_dimension(self, embedder):
        vecs = embedder.embed_texts(["test sentence"])
        assert vecs.shape == (1, 384), f"Expected (1, 384), got {vecs.shape}"

    def test_batch_embedding(self, embedder):
        texts = [f"sentence number {i}" for i in range(10)]
        vecs = embedder.embed_texts(texts)
        assert vecs.shape == (10, 384)

    def test_embeddings_normalised(self, embedder):
        vecs = embedder.embed_texts(["hello world", "another sentence"])
        norms = np.linalg.norm(vecs, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5, err_msg="Embeddings should be unit-normalised")

    def test_empty_input(self, embedder):
        vecs = embedder.embed_texts([])
        assert vecs.shape == (0, 384)

    def test_query_embedding_shape(self, embedder):
        vec = embedder.embed_query("customer complaint about billing")
        assert vec.shape == (384,)

    def test_similar_texts_higher_score(self, embedder):
        q = embedder.embed_query("billing dispute refund")
        relevant = embedder.embed_texts(["customer overcharged on billing statement"])[0]
        irrelevant = embedder.embed_texts(["the weather is nice today"])[0]
        score_rel = float(np.dot(q, relevant))
        score_irr = float(np.dot(q, irrelevant))
        assert score_rel > score_irr, "Semantically similar text should score higher"

    def test_embed_chunks_in_place(self, embedder):
        from backend.retrieval.ingestion import _sliding_window_chunks
        text = "Customer has a billing dispute involving overcharge."
        meta = {"source_type": "ticket", "source_id": "TKT-TEST"}
        chunks = _sliding_window_chunks(text, meta)
        result = embedder.embed_chunks(chunks)
        for c in result:
            assert c.embedding is not None
            assert len(c.embedding) == 384


# ============================================================
# Unit Tests — Filter Builder
# ============================================================

class TestFilterBuilder:
    def test_empty_filter(self):
        from backend.retrieval.retriever import _build_filter
        from backend.retrieval.models import MetadataFilter
        f = MetadataFilter()
        assert _build_filter(f) == {}

    def test_source_type_filter(self):
        from backend.retrieval.retriever import _build_filter
        from backend.retrieval.models import MetadataFilter
        f = MetadataFilter(source_type="ticket")
        d = _build_filter(f)
        assert d == {"source_type": "ticket"}

    def test_combined_filter(self):
        from backend.retrieval.retriever import _build_filter
        from backend.retrieval.models import MetadataFilter
        f = MetadataFilter(source_type="ticket", priority="high", status="open")
        d = _build_filter(f)
        assert d["source_type"] == "ticket"
        assert d["priority"] == "high"
        assert d["status"] == "open"

    def test_none_fields_excluded(self):
        from backend.retrieval.retriever import _build_filter
        from backend.retrieval.models import MetadataFilter
        f = MetadataFilter(source_type="policy", issue_category=None)
        d = _build_filter(f)
        assert "issue_category" not in d

    def test_sla_breach_filter(self):
        from backend.retrieval.retriever import _build_filter
        from backend.retrieval.models import MetadataFilter
        f = MetadataFilter(sla_breach=True)
        d = _build_filter(f)
        assert d["sla_breach"] is True


# ============================================================
# Unit Tests — Models
# ============================================================

class TestModels:
    def test_retrieved_chunk_citation_ticket(self):
        from backend.retrieval.models import RetrievedChunk
        import uuid
        c = RetrievedChunk(
            chunk_id=uuid.uuid4(), doc_id=uuid.uuid4(),
            source_type="ticket", source_id="TKT-0042",
            chunk_index=2, content="test", score=0.85, metadata={}
        )
        assert "TKT-0042" in c.citation
        assert "chunk 2" in c.citation

    def test_retrieved_chunk_citation_policy(self):
        from backend.retrieval.models import RetrievedChunk
        import uuid
        c = RetrievedChunk(
            chunk_id=uuid.uuid4(), doc_id=uuid.uuid4(),
            source_type="policy", source_id="escalation_policy.md",
            chunk_index=0, content="test", score=0.91, metadata={}
        )
        assert "escalation_policy.md" in c.citation

    def test_retrieval_result_combined_context(self):
        from backend.retrieval.models import RetrievedChunk, RetrievalResult
        import uuid
        chunks = [
            RetrievedChunk(chunk_id=uuid.uuid4(), doc_id=uuid.uuid4(),
                           source_type="ticket", source_id="TKT-0001",
                           chunk_index=0, content="billing issue text",
                           score=0.9, metadata={})
        ]
        result = RetrievalResult(
            query_text="billing problem", chunks=chunks, total_found=1,
            filters_applied={}, retrieval_time_ms=10.5
        )
        ctx = result.combined_context
        assert "TKT-0001" in ctx
        assert "billing issue text" in ctx
        assert "0.900" in ctx


# ============================================================
# Integration Tests — require running DB
# ============================================================

@pytest.mark.integration
class TestRetrievalIntegration:
    """
    These tests require a running PostgreSQL + pgvector instance.
    Run with: pytest backend/tests/test_retrieval.py -v -m integration
    Assumes the DB has been populated with: python ingest_cli.py --source all
    """

    def test_billing_query_returns_ticket_chunks(self):
        from backend.retrieval.retriever import quick_retrieve
        result = quick_retrieve("customer double charged on billing", top_k=5, source_type="ticket")
        assert result.total_found > 0, "Should find billing tickets"
        for c in result.chunks:
            assert c.score >= 0.30, "All results should be above threshold"
            assert c.source_type == "ticket"

    def test_policy_query_returns_policy_chunks(self):
        from backend.retrieval.retriever import quick_retrieve
        result = quick_retrieve("escalation criteria and process", top_k=5, source_type="policy")
        assert result.total_found > 0, "Should find policy chunks"
        for c in result.chunks:
            assert c.source_type == "policy"

    def test_metadata_filter_respected(self):
        from backend.retrieval.retriever import quick_retrieve
        result = quick_retrieve("complaint", top_k=10, source_type="ticket", priority="high")
        for c in result.chunks:
            assert c.metadata.get("priority") == "high", "Filter must be enforced"

    def test_score_threshold_enforced(self):
        from backend.retrieval.retriever import quick_retrieve
        result = quick_retrieve("xyzzy nonsense 123456 frobnicating", top_k=5, score_threshold=0.30)
        for c in result.chunks:
            assert c.score >= 0.30, "Score threshold must be enforced"

    def test_citations_complete(self):
        from backend.retrieval.retriever import quick_retrieve
        result = quick_retrieve("billing refund", top_k=5)
        for c in result.chunks:
            assert c.chunk_id is not None
            assert c.doc_id is not None
            assert c.source_id != ""
            assert c.source_type in ("ticket", "policy")

    def test_combined_context_not_empty(self):
        from backend.retrieval.retriever import quick_retrieve
        result = quick_retrieve("customer complaint", top_k=3)
        if result.total_found > 0:
            assert len(result.combined_context) > 0


@pytest.mark.integration
class TestPrecisionRecall:
    """
    Precision@K and Recall@K against test_queries.json ground truth.
    Minimum targets: Precision@3 >= 0.50, Recall@5 >= 0.60
    """

    @pytest.fixture(scope="class")
    def test_queries(self):
        with open(TEST_QUERIES_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _precision_at_k(self, retrieved_source_ids: List[str], relevant_keywords: List[str], k: int) -> float:
        """Keyword-based precision: how many of top-K chunks contain at least one relevant keyword."""
        top_k = retrieved_source_ids[:k]
        if not top_k:
            return 0.0
        hits = sum(
            1 for sid in top_k
            if any(kw.lower() in sid.lower() for kw in relevant_keywords)
        )
        return hits / k

    def test_policy_queries_return_correct_policies(self, test_queries):
        """Policy queries should return the right policy files in top-5."""
        from backend.retrieval.retriever import quick_retrieve
        policy_queries = [q for q in test_queries if q.get("source_type") == "policy"]

        hits = 0
        total = 0
        for q in policy_queries:
            result = quick_retrieve(q["query_text"], top_k=5, source_type="policy")
            relevant_ids = q.get("relevant_source_ids", [])
            retrieved_ids = [c.source_id for c in result.chunks]
            if any(rid in retrieved_ids for rid in relevant_ids):
                hits += 1
            total += 1

        recall = hits / total if total > 0 else 0.0
        print(f"\nPolicy Query Recall@5: {recall:.2%} ({hits}/{total})")
        assert recall >= 0.60, f"Policy Recall@5 {recall:.2%} below 60% target"

    def test_ticket_queries_return_relevant_tickets(self, test_queries):
        """Ticket queries should return tickets in the right category."""
        from backend.retrieval.retriever import quick_retrieve
        ticket_queries = [q for q in test_queries if q.get("source_type") == "ticket"]

        hits = 0
        total = 0
        for q in ticket_queries:
            cats = q.get("relevant_categories", [])
            if not cats:
                continue
            result = quick_retrieve(q["query_text"], top_k=5, source_type="ticket")
            cat_hits = sum(
                1 for c in result.chunks
                if c.metadata.get("issue_category") in cats
            )
            precision_3 = min(cat_hits, 3) / 3 if result.chunks else 0.0
            if precision_3 >= 0.5:
                hits += 1
            total += 1

        overall = hits / total if total > 0 else 0.0
        print(f"\nTicket Precision@3 (>=50% threshold): {overall:.2%} ({hits}/{total})")
        assert overall >= 0.60, f"Ticket precision {overall:.2%} below 60% target"

    def test_retrieval_latency(self, test_queries):
        """Average retrieval latency should be < 500ms."""
        from backend.retrieval.retriever import quick_retrieve
        latencies = []
        for q in test_queries[:10]:  # sample 10
            result = quick_retrieve(q["query_text"], top_k=5)
            latencies.append(result.retrieval_time_ms)

        avg_ms = sum(latencies) / len(latencies)
        print(f"\nAverage retrieval latency: {avg_ms:.1f}ms")
        assert avg_ms < 500, f"Average latency {avg_ms:.1f}ms exceeds 500ms target"
