"""
FlowMind AI - Tests for Execution Connector & Audit Service (Phase 3)
Verifies:
  1. Connector idempotency and simulated subsystems.
  2. Fix 2: Conditional audit completeness per terminal state (COMPLETED, AUTO_EXECUTED, REJECTED, ABSTAINED).
  3. Tamper-evident JSON audit trail export.
"""
import uuid
import pytest

from backend.audit.models import AuditRecord
from backend.audit.service import AuditService
from backend.connectors.base import ExecutionRequest
from backend.connectors.mock_connector import MockEnterpriseConnector
from backend.reasoning.models import ActionType, EscalationLevel, NextBestAction


class TestMockEnterpriseConnector:

    def test_idempotent_execution_replays_existing_transaction(self):
        connector = MockEnterpriseConnector(simulate_latency_ms=0.0)
        action = NextBestAction(
            action_type=ActionType.ESCALATE_TICKET,
            target_team="Finance Team",
            escalation_level=EscalationLevel.L2,
            requires_approval=True,
        )
        req = ExecutionRequest(
            workflow_id="WF-IDEMP-001",
            action=action,
            approver_id="USR-003",
            approver_role="manager",
            approval_token="APP-VERIFIED-WF-IDEMP-001",
        )

        # First execution creates transaction
        res1 = connector.execute(req)
        assert res1.status == "SUCCESS"
        assert res1.is_idempotent_replay is False
        first_tx = res1.transaction_id

        # Second execution for identical workflow ID returns cached transaction
        res2 = connector.execute(req)
        assert res2.status == "SUCCESS"
        assert res2.is_idempotent_replay is True
        assert res2.transaction_id == first_tx

    def test_failure_simulation_mode(self):
        connector = MockEnterpriseConnector(simulate_latency_ms=0.0, fail_on_purpose=True)
        action = NextBestAction(action_type=ActionType.RESOLVE_STANDARD, target_team="Support")
        req = ExecutionRequest(workflow_id="WF-FAIL-001", action=action, is_auto_executed=True)

        res = connector.execute(req)
        assert res.status == "FAILED"
        assert "ERR-" in res.transaction_id


class TestAuditCompletenessFix2:
    """
    Fix 2 Test: Conditional audit completeness invariant across all terminal states.
    """

    def test_completed_workflow_audit_completeness(self):
        # A human-approved COMPLETED workflow must have approval + execution records
        record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            workflow_id="WF-COMPLETED-001",
            terminal_state="COMPLETED",
            started_at="2026-09-08T10:00:00Z",
            completed_at="2026-09-08T10:00:02Z",
            request_payload={"customer_id": "CUST-1001", "issue_summary": "Test"},
            retrieval_summary={"total_retrieved": 3},
            evidence_citations=[{"source_id": "TKT-001"}],
            reasoning_output={"status": "RECOMMENDATION_READY"},
            approval_record={"decision": "APPROVE", "approver_id": "USR-003"},
            execution_record={"status": "SUCCESS", "transaction_id": "TKT-ESC-1234"},
        )
        assert record.is_complete is True

        # Incomplete if approval is missing
        record_missing_approval = record.model_copy(update={"approval_record": None})
        assert record_missing_approval.is_complete is False

        # Incomplete if execution is missing
        record_missing_exec = record.model_copy(update={"execution_record": None})
        assert record_missing_exec.is_complete is False

    def test_auto_executed_workflow_audit_completeness(self):
        # AUTO_EXECUTED legitimately has NO approval record
        record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            workflow_id="WF-AUTO-001",
            terminal_state="AUTO_EXECUTED",
            started_at="2026-09-08T10:00:00Z",
            completed_at="2026-09-08T10:00:01Z",
            request_payload={"customer_id": "CUST-1020", "issue_summary": "Delivery inquiry"},
            retrieval_summary={"total_retrieved": 2},
            evidence_citations=[{"source_id": "TKT-0010"}],
            reasoning_output={"status": "RECOMMENDATION_READY"},
            approval_record=None,  # No approval!
            execution_record={"status": "SUCCESS", "transaction_id": "RES-STD-5678"},
        )
        # Must be marked complete without a false missing-approval flag
        assert record.is_complete is True

    def test_rejected_workflow_audit_completeness(self):
        # REJECTED workflow must have rejection reason and legitimately NO execution record
        record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            workflow_id="WF-REJ-001",
            terminal_state="REJECTED",
            started_at="2026-09-08T10:00:00Z",
            completed_at="2026-09-08T10:00:01Z",
            request_payload={"customer_id": "CUST-1045", "issue_summary": "Threat"},
            retrieval_summary={"total_retrieved": 4},
            evidence_citations=[{"source_id": "TKT-0045"}],
            reasoning_output={"status": "RECOMMENDATION_READY"},
            approval_record={"decision": "REJECT", "approver_id": "USR-003", "rejection_reason": "Out of scope."},
            execution_record=None,  # No execution!
        )
        assert record.is_complete is True

    def test_abstained_workflow_audit_completeness(self):
        # ABSTAINED workflow has reasoning output but legitimately NO approval and NO execution
        record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            workflow_id="WF-ABST-001",
            terminal_state="ABSTAINED",
            started_at="2026-09-08T10:00:00Z",
            completed_at="2026-09-08T10:00:01Z",
            request_payload={"customer_id": "CUST-9999", "issue_summary": "Unknown"},
            retrieval_summary={"total_retrieved": 0},
            evidence_citations=[],
            reasoning_output={"status": "ABSTAINED", "abstention_reason": "INSUFFICIENT_EVIDENCE"},
            approval_record=None,
            execution_record=None,
        )
        assert record.is_complete is True


class TestAuditServiceExport:

    def test_audit_trail_export_structure(self):
        service = AuditService()
        wf_id = "WF-EXPORT-001"
        record = AuditRecord(
            audit_id="AUD-001",
            workflow_id=wf_id,
            terminal_state="COMPLETED",
            started_at="2026-09-08T10:00:00Z",
            completed_at="2026-09-08T10:00:02Z",
            duration_ms=2000.0,
            request_payload={"customer_id": "CUST-1002"},
            retrieval_summary={"chunks": 2},
            evidence_citations=[],
            reasoning_output={"action": "ESCALATE"},
            approval_record={"decision": "APPROVE", "approver_id": "USR-003"},
            execution_record={"status": "SUCCESS", "transaction_id": "TX-01"},
        )
        service.record_audit(record)

        trail = service.export_audit_trail(wf_id)
        assert trail["audit_id"] == "AUD-001"
        assert trail["workflow_id"] == wf_id
        assert trail["terminal_state"] == "COMPLETED"
        assert "timeline" in trail
        assert "investigation" in trail
        assert "human_governance" in trail
        assert "automation_execution" in trail
