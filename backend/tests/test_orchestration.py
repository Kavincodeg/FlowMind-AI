"""
FlowMind AI - Tests for Workflow Orchestrator & State Machine (Phase 3)
Verifies:
  1. Complete lifecycle state transitions (Approved, Rejected, Modified, Abstained).
  2. Fix 1: RBAC validation on modified actions inside orchestrator.
  3. Fix 3: Auto-execute path for clean routine actions bypassing PENDING_APPROVAL.
  4. Direct execution guard (UnauthorizedExecutionError).
"""
import pytest

from backend.audit.service import AuditService
from backend.connectors.base import ExecutionRequest, UnauthorizedExecutionError
from backend.connectors.mock_connector import MockEnterpriseConnector
from backend.orchestrator.models import (
    ApprovalDecisionType,
    ApprovalSubmission,
    WorkflowStatus,
)
from backend.orchestrator.orchestrator import WorkflowOrchestrator
from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.models import (
    ActionType,
    ComplaintInvestigationRequest,
    EscalationLevel,
    NextBestAction,
)
from backend.security.models import PRECONFIGURED_PERSONAS, UserContext, UserRole
from backend.security.rbac import RBACPermissionDeniedError


@pytest.fixture
def test_setup():
    audit_service = AuditService()
    connector = MockEnterpriseConnector(simulate_latency_ms=0.0)
    orchestrator = WorkflowOrchestrator(
        connector=connector,
        audit_service=audit_service,
    )
    agent_user = PRECONFIGURED_PERSONAS["flowmind-agent-token-001"]
    lead_user = PRECONFIGURED_PERSONAS["flowmind-lead-token-002"]
    mgr_user = PRECONFIGURED_PERSONAS["flowmind-mgr-token-003"]
    admin_user = PRECONFIGURED_PERSONAS["flowmind-admin-token-004"]
    return {
        "orchestrator": orchestrator,
        "audit_service": audit_service,
        "connector": connector,
        "agent": agent_user,
        "lead": lead_user,
        "manager": mgr_user,
        "admin": admin_user,
    }


class TestWorkflowStateTransitions:

    def test_happy_path_investigate_approve_execute(self, test_setup):
        """Full human-governed happy path: SUBMITTED -> PENDING_APPROVAL -> APPROVED -> COMPLETED."""
        orch = test_setup["orchestrator"]
        mgr = test_setup["manager"]
        agent = test_setup["agent"]

        # Sensitive repeat contact complaint triggers L2 escalation
        req = ComplaintInvestigationRequest(
            customer_id="CUST-1002",
            customer_name="Arjun Sharma",
            issue_summary="Damaged goods reported for fourth time. Escalation required.",
        )
        instance = orch.start_investigation(req, requester=agent)

        # Must pause at PENDING_APPROVAL
        assert instance.status == WorkflowStatus.PENDING_APPROVAL
        assert instance.reasoning_output is not None
        assert instance.reasoning_output.requires_human_approval is True
        assert instance.reasoning_output.recommendation is not None
        assert instance.reasoning_output.recommendation.action_type == ActionType.ESCALATE_TICKET

        # Manager approves
        submission = ApprovalSubmission(
            decision=ApprovalDecisionType.APPROVE,
            comments="Approved per escalation policy trigger 2.",
        )
        completed = orch.submit_approval(instance.workflow_id, submission, approver=mgr)

        assert completed.status == WorkflowStatus.COMPLETED
        assert completed.approval_record is not None
        assert completed.approval_record["decision"] == "APPROVE"
        assert completed.approval_record["approver_id"] == mgr.user_id
        assert completed.execution_record is not None
        assert completed.execution_record.status == "SUCCESS"
        assert "TKT-ESC-" in completed.execution_record.transaction_id

    def test_rejection_path_halts_without_execution(self, test_setup):
        """Rejection path: PENDING_APPROVAL -> REJECTED. No connector execution occurs."""
        orch = test_setup["orchestrator"]
        mgr = test_setup["manager"]
        agent = test_setup["agent"]

        req = ComplaintInvestigationRequest(
            customer_id="CUST-1045",
            customer_name="Priya Nair",
            issue_summary="Customer threatening legal action over invoice error.",
        )
        instance = orch.start_investigation(req, requester=agent)
        assert instance.status == WorkflowStatus.PENDING_APPROVAL

        # Rejection requires reason
        with pytest.raises(ValueError, match="rejection reason must be provided"):
            orch.submit_approval(
                instance.workflow_id,
                ApprovalSubmission(decision=ApprovalDecisionType.REJECT, rejection_reason=""),
                approver=mgr,
            )

        # Reject with valid reason
        rejected = orch.submit_approval(
            instance.workflow_id,
            ApprovalSubmission(decision=ApprovalDecisionType.REJECT, rejection_reason="Legal team already directly engaged."),
            approver=mgr,
        )

        assert rejected.status == WorkflowStatus.REJECTED
        assert rejected.approval_record["decision"] == "REJECT"
        assert rejected.approval_record["rejection_reason"] == "Legal team already directly engaged."
        # Crucial non-negotiable: no execution was dispatched
        assert rejected.execution_record is None

    def test_modification_path_executes_modified_action(self, test_setup):
        """Modification path: Approver modifies target team and urgency before execution."""
        orch = test_setup["orchestrator"]
        mgr = test_setup["manager"]
        agent = test_setup["agent"]

        req = ComplaintInvestigationRequest(
            customer_id="CUST-1008",
            customer_name="Elena Rostova",
            issue_summary="Duplicate billing charge dispute.",
        )
        instance = orch.start_investigation(req, requester=agent)
        assert instance.status == WorkflowStatus.PENDING_APPROVAL

        # Manager modifies target team to Senior Finance and urgency to critical
        modified = NextBestAction(
            action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
            target_team="Senior Finance Team",
            urgency="critical",
            parameters={"verified_duplicate_id": "TX-9941"},
            requires_approval=True,
        )
        submission = ApprovalSubmission(
            decision=ApprovalDecisionType.MODIFY,
            modified_action=modified,
            comments="Elevating urgency to critical due to VIP customer status.",
        )
        completed = orch.submit_approval(instance.workflow_id, submission, approver=mgr)

        assert completed.status == WorkflowStatus.COMPLETED
        assert completed.approval_record["decision"] == "MODIFY"
        assert completed.approval_record["modified_action"]["target_team"] == "Senior Finance Team"
        assert completed.execution_record.details["finance_queue"] == "Senior Finance Team"

    def test_fix_1_orchestrator_blocks_unauthorized_modification(self, test_setup):
        """
        Fix 1 Test: Team lead attempts to modify an action into an L3 escalation.
        Orchestrator must reject the submission via RBAC check on the modified action.
        """
        orch = test_setup["orchestrator"]
        lead = test_setup["lead"]
        agent = test_setup["agent"]

        req = ComplaintInvestigationRequest(
            customer_id="CUST-1019",
            customer_name="Emily Watson",
            issue_summary="Delivery SLA breach single ticket.",
        )
        instance = orch.start_investigation(req, requester=agent)
        assert instance.status == WorkflowStatus.PENDING_APPROVAL

        # Lead attempts to escalate to L3 (which requires Manager or Admin)
        unauthorized_mod = NextBestAction(
            action_type=ActionType.ESCALATE_TICKET,
            target_team="Executive Escalations",
            escalation_level=EscalationLevel.L3,
            urgency="critical",
            requires_approval=True,
        )
        submission = ApprovalSubmission(
            decision=ApprovalDecisionType.MODIFY,
            modified_action=unauthorized_mod,
            comments="Attempting to force L3 escalation.",
        )

        with pytest.raises(RBACPermissionDeniedError) as exc_info:
            orch.submit_approval(instance.workflow_id, submission, approver=lead)

        assert "Requires Manager or Admin" in exc_info.value.reason
        # Workflow state remains PENDING_APPROVAL
        assert orch.get_workflow(instance.workflow_id).status == WorkflowStatus.PENDING_APPROVAL

    def test_fix_3_auto_execute_path_for_routine_action(self, test_setup):
        """
        Fix 3 Test: Routine action (RESOLVE_STANDARD) without injection threat qualifies
        for auto-execution, transitioning directly to COMPLETED without entering PENDING_APPROVAL.
        """
        orch = test_setup["orchestrator"]
        agent = test_setup["agent"]

        # Single occurrence delivery question within SLA (CASE-006 pattern)
        req = ComplaintInvestigationRequest(
            customer_id="CUST-1020",
            customer_name="Sarah Connor",
            issue_summary="Delivery estimate inquiry for package shipped yesterday. Single contact.",
        )
        instance = orch.start_investigation(req, requester=agent)

        # Non-negotiable invariant: must NOT pause at PENDING_APPROVAL
        assert instance.status == WorkflowStatus.COMPLETED
        assert instance.reasoning_output.requires_human_approval is False
        assert instance.approval_record is None  # Legitimately no approver
        assert instance.execution_record is not None
        assert instance.execution_record.status == "SUCCESS"
        assert "RES-STD-" in instance.execution_record.transaction_id

    def test_abstention_transitions_directly_to_abstained(self, test_setup):
        """Zero evidence triggers early abstention directly into ABSTAINED terminal state."""
        orch = test_setup["orchestrator"]
        agent = test_setup["agent"]

        req = ComplaintInvestigationRequest(
            customer_id="CUST-9999",
            customer_name="Unknown User",
            issue_summary="Zero customer tickets or history in database.",
        )
        instance = orch.start_investigation(req, requester=agent)

        assert instance.status == WorkflowStatus.ABSTAINED
        assert instance.reasoning_output.is_abstention is True
        assert instance.approval_record is None
        assert instance.execution_record is None

    def test_direct_execution_guard_raises_unauthorized(self, test_setup):
        """
        Attempting to invoke connector.execute without an approval token
        and without is_auto_executed=True raises UnauthorizedExecutionError.
        """
        connector = test_setup["connector"]
        action = NextBestAction(
            action_type=ActionType.ESCALATE_TICKET,
            target_team="Operations Team",
            escalation_level=EscalationLevel.L2,
            urgency="high",
            requires_approval=True,
        )

        unauthorized_req = ExecutionRequest(
            workflow_id="WF-ROGUE-001",
            action=action,
            is_auto_executed=False,
            approval_token=None,  # Missing approval token!
        )

        with pytest.raises(UnauthorizedExecutionError, match="cannot execute without human approval verification"):
            connector.execute(unauthorized_req)
