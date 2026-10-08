"""
FlowMind AI - Task 1 Security Fix Tests

Tests that verify the retrieval failure path causes a FAILED workflow,
never PENDING_APPROVAL, AUTO_EXECUTED, or COMPLETED.

These tests go through the REAL retrieve() path (not mock injection).
ann_search is patched to raise an exception to simulate DB unavailability.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from backend.connectors.mock_connector import MockEnterpriseConnector
from backend.audit.service import AuditService
from backend.orchestrator.orchestrator import WorkflowOrchestrator
from backend.orchestrator.models import WorkflowStatus
from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.models import ComplaintInvestigationRequest
from backend.retrieval.retriever import RetrievalUnavailableError
from backend.security.models import PRECONFIGURED_PERSONAS


AGENT = PRECONFIGURED_PERSONAS["flowmind-agent-token-001"]


class TestRetrievalFailureCausesFailedWorkflow:
    """
    Task 1 invariant: when ann_search raises (database unreachable), the workflow
    must end in FAILED – never PENDING_APPROVAL, AUTO_EXECUTED, or COMPLETED –
    and no citations or recommendation may be present.
    """

    def _make_orchestrator(self) -> WorkflowOrchestrator:
        """Build an orchestrator that uses the REAL retrieve() (no mock injection)."""
        return WorkflowOrchestrator(
            reasoning_engine=ReasoningEngine(),  # uses default_retrieve internally
            connector=MockEnterpriseConnector(simulate_latency_ms=0.0),
            audit_service=AuditService(),
        )

    def test_db_down_investigation_ends_in_failed(self):
        """
        Patch ann_search to raise so the real retrieve() propagates
        RetrievalUnavailableError, which the reasoning engine catches and
        returns status=ERROR, which the orchestrator must convert to FAILED.
        """
        orch = self._make_orchestrator()

        request = ComplaintInvestigationRequest(
            customer_id="CUST-TEST-DBDOWN",
            customer_name="Test Customer",
            issue_summary="Billing dispute for subscription overcharge.",
        )

        with patch("backend.retrieval.store.ann_search") as mock_ann:
            mock_ann.side_effect = Exception("FATAL: connection refused (database down)")

            instance = orch.start_investigation(request, requester=AGENT)

        # Core invariant: must be FAILED, never anything that implies data was available
        assert instance.status == WorkflowStatus.FAILED, (
            f"Expected FAILED but got {instance.status}. "
            "The workflow silently proceeded without real evidence."
        )
        assert instance.status not in (
            WorkflowStatus.PENDING_APPROVAL,
            WorkflowStatus.AUTO_EXECUTED,
            WorkflowStatus.COMPLETED,
        ), "Workflow must not progress to approval or completion when DB is down."

    def test_db_down_no_citations_or_recommendation(self):
        """When the DB is down, no citations or recommendation must appear in the output."""
        orch = self._make_orchestrator()

        request = ComplaintInvestigationRequest(
            customer_id="CUST-TEST-DBDOWN-2",
            customer_name="Test Customer B",
            issue_summary="Refund request for double billing.",
        )

        with patch("backend.retrieval.store.ann_search") as mock_ann:
            mock_ann.side_effect = Exception("connection timed out")

            instance = orch.start_investigation(request, requester=AGENT)

        ro = instance.reasoning_output
        assert ro is not None, "reasoning_output should be set even on failure"

        citations = ro.citations if ro else []
        recommendation = ro.recommendation if ro else None

        assert len(citations) == 0, (
            f"Expected no citations when DB is down, but got {len(citations)}: {citations}"
        )
        assert recommendation is None, (
            f"Expected no recommendation when DB is down, but got: {recommendation}"
        )

    def test_retrieve_raises_retrieval_unavailable_error_on_db_failure(self):
        """
        Unit test: retrieve() must raise RetrievalUnavailableError (not return mock data)
        when ann_search raises any exception.
        """
        from backend.retrieval.retriever import retrieve, RetrievalUnavailableError
        from backend.retrieval.models import MetadataFilter, RetrievalQuery

        rq = RetrievalQuery(
            query_text="billing dispute",
            top_k=5,
            filters=MetadataFilter(),
            score_threshold=0.30,
        )

        with patch("backend.retrieval.store.ann_search") as mock_ann:
            mock_ann.side_effect = Exception("connection refused")

            with pytest.raises(RetrievalUnavailableError) as exc_info:
                retrieve(rq)

        assert "connection refused" in str(exc_info.value).lower() or "unreachable" in str(exc_info.value).lower()
