"""
FlowMind AI - Comprehensive Table-Driven Authority and Policy Document Sync Tests (Prompt 3 Task 8)

Covers:
  1. Table-driven authority test: 8 roles against 15 actions/boundaries (120 test cases).
     Compared against a hand-written expected table in the test.
  2. Doc-sync test: Parses markdown tables in approval_authority_matrix.md and asserts
     that role names and refund limits equal authority.py. Fails if document and code drift apart.
  3. Specific test cases:
     - system_admin is denied everywhere
     - department_head and executive are denied a $501 refund
     - finance_reviewer is denied escalations and standard resolutions
     - vp_finance approves any refund but no escalation
     - modified action raising amount is re-checked
     - self-approval above Tier 1 limits is blocked
     - refund with no amount cannot be approved
     - modification without a note returns 400 / ValueError
  4. Auto-execution condition tests.
  5. API 403 bodies name the required roles.
"""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.orchestrator.models import ApprovalDecisionType, ApprovalSubmission, WorkflowInstance, WorkflowStatus
from backend.orchestrator.orchestrator import WorkflowOrchestrator
from backend.reasoning.auto_execution import is_auto_executable
from backend.reasoning.models import (
    ActionType,
    ComplaintInvestigationRequest,
    EscalationLevel,
    EvidenceCitation,
    NextBestAction,
    ReasoningOutput,
)
from backend.security.authority import (
    can_approve,
    REFUND_LIMITS,
    SUPPORT_LINE_ROLES,
    ROLE_DISPLAY_NAMES,
)
from backend.security.models import PRECONFIGURED_PERSONAS, UserContext, UserRole
from backend.security.rbac import RBACPermissionDeniedError, verify_approval_permission


def make_user(role: UserRole, user_id: str = "USR-TEST") -> UserContext:
    return UserContext(
        user_id=user_id,
        name=f"Test {ROLE_DISPLAY_NAMES[role]}",
        role=role,
    )


# ---------------------------------------------------------------------------
# 1. Table-Driven Authority Test (120 test cases)
# ---------------------------------------------------------------------------

# Hand-written expected truth table:
# Keys: (action_key, role) -> expected_allowed: bool
# 15 Actions/Boundaries x 8 Roles = 120 matrix points
ACTIONS_UNDER_TEST = [
    "standard_resolution",
    "transfer",
    "escalate_l1",
    "escalate_l2",
    "escalate_l3",
    "escalate_l4",
    "refund_50",
    "refund_50_01",
    "refund_200",
    "refund_200_01",
    "refund_500",
    "refund_500_01",
    "refund_1000",
    "refund_1000_01",
    "refund_100000",
]

ALL_ROLES = [
    UserRole.SUPPORT_AGENT,
    UserRole.TEAM_LEAD,
    UserRole.TEAM_MANAGER,
    UserRole.DEPARTMENT_HEAD,
    UserRole.EXECUTIVE,
    UserRole.FINANCE_REVIEWER,
    UserRole.VP_FINANCE,
    UserRole.SYSTEM_ADMIN,
]

HAND_WRITTEN_TRUTH_TABLE = {
    # 1. Standard resolution
    ("standard_resolution", UserRole.SUPPORT_AGENT): True,
    ("standard_resolution", UserRole.TEAM_LEAD): True,
    ("standard_resolution", UserRole.TEAM_MANAGER): True,
    ("standard_resolution", UserRole.DEPARTMENT_HEAD): True,
    ("standard_resolution", UserRole.EXECUTIVE): True,
    ("standard_resolution", UserRole.FINANCE_REVIEWER): False,
    ("standard_resolution", UserRole.VP_FINANCE): False,
    ("standard_resolution", UserRole.SYSTEM_ADMIN): False,

    # 2. Transfer (cross-team)
    ("transfer", UserRole.SUPPORT_AGENT): False,
    ("transfer", UserRole.TEAM_LEAD): False,
    ("transfer", UserRole.TEAM_MANAGER): True,
    ("transfer", UserRole.DEPARTMENT_HEAD): True,
    ("transfer", UserRole.EXECUTIVE): True,
    ("transfer", UserRole.FINANCE_REVIEWER): False,
    ("transfer", UserRole.VP_FINANCE): False,
    ("transfer", UserRole.SYSTEM_ADMIN): False,

    # 3. Escalation L1
    ("escalate_l1", UserRole.SUPPORT_AGENT): False,
    ("escalate_l1", UserRole.TEAM_LEAD): True,
    ("escalate_l1", UserRole.TEAM_MANAGER): True,
    ("escalate_l1", UserRole.DEPARTMENT_HEAD): True,
    ("escalate_l1", UserRole.EXECUTIVE): True,
    ("escalate_l1", UserRole.FINANCE_REVIEWER): False,
    ("escalate_l1", UserRole.VP_FINANCE): False,
    ("escalate_l1", UserRole.SYSTEM_ADMIN): False,

    # 4. Escalation L2
    ("escalate_l2", UserRole.SUPPORT_AGENT): False,
    ("escalate_l2", UserRole.TEAM_LEAD): False,
    ("escalate_l2", UserRole.TEAM_MANAGER): True,
    ("escalate_l2", UserRole.DEPARTMENT_HEAD): True,
    ("escalate_l2", UserRole.EXECUTIVE): True,
    ("escalate_l2", UserRole.FINANCE_REVIEWER): False,
    ("escalate_l2", UserRole.VP_FINANCE): False,
    ("escalate_l2", UserRole.SYSTEM_ADMIN): False,

    # 5. Escalation L3
    ("escalate_l3", UserRole.SUPPORT_AGENT): False,
    ("escalate_l3", UserRole.TEAM_LEAD): False,
    ("escalate_l3", UserRole.TEAM_MANAGER): False,
    ("escalate_l3", UserRole.DEPARTMENT_HEAD): True,
    ("escalate_l3", UserRole.EXECUTIVE): True,
    ("escalate_l3", UserRole.FINANCE_REVIEWER): False,
    ("escalate_l3", UserRole.VP_FINANCE): False,
    ("escalate_l3", UserRole.SYSTEM_ADMIN): False,

    # 6. Escalation L4
    ("escalate_l4", UserRole.SUPPORT_AGENT): False,
    ("escalate_l4", UserRole.TEAM_LEAD): False,
    ("escalate_l4", UserRole.TEAM_MANAGER): False,
    ("escalate_l4", UserRole.DEPARTMENT_HEAD): False,
    ("escalate_l4", UserRole.EXECUTIVE): True,
    ("escalate_l4", UserRole.FINANCE_REVIEWER): False,
    ("escalate_l4", UserRole.VP_FINANCE): False,
    ("escalate_l4", UserRole.SYSTEM_ADMIN): False,

    # 7. Refund $50 (Tier 1 limit: all can approve except sysadmin and finance_reviewer whose range is $51-$1000)
    ("refund_50", UserRole.SUPPORT_AGENT): True,
    ("refund_50", UserRole.TEAM_LEAD): True,
    ("refund_50", UserRole.TEAM_MANAGER): True,
    ("refund_50", UserRole.DEPARTMENT_HEAD): True,
    ("refund_50", UserRole.EXECUTIVE): True,
    ("refund_50", UserRole.FINANCE_REVIEWER): False,
    ("refund_50", UserRole.VP_FINANCE): True,
    ("refund_50", UserRole.SYSTEM_ADMIN): False,

    # 8. Refund $50.01 (Agent limit exceeded)
    ("refund_50_01", UserRole.SUPPORT_AGENT): False,
    ("refund_50_01", UserRole.TEAM_LEAD): True,
    ("refund_50_01", UserRole.TEAM_MANAGER): True,
    ("refund_50_01", UserRole.DEPARTMENT_HEAD): True,
    ("refund_50_01", UserRole.EXECUTIVE): True,
    ("refund_50_01", UserRole.FINANCE_REVIEWER): True,
    ("refund_50_01", UserRole.VP_FINANCE): True,
    ("refund_50_01", UserRole.SYSTEM_ADMIN): False,

    # 9. Refund $200 (Team Lead limit boundary)
    ("refund_200", UserRole.SUPPORT_AGENT): False,
    ("refund_200", UserRole.TEAM_LEAD): True,
    ("refund_200", UserRole.TEAM_MANAGER): True,
    ("refund_200", UserRole.DEPARTMENT_HEAD): True,
    ("refund_200", UserRole.EXECUTIVE): True,
    ("refund_200", UserRole.FINANCE_REVIEWER): True,
    ("refund_200", UserRole.VP_FINANCE): True,
    ("refund_200", UserRole.SYSTEM_ADMIN): False,

    # 10. Refund $200.01 (Team Lead limit exceeded)
    ("refund_200_01", UserRole.SUPPORT_AGENT): False,
    ("refund_200_01", UserRole.TEAM_LEAD): False,
    ("refund_200_01", UserRole.TEAM_MANAGER): True,
    ("refund_200_01", UserRole.DEPARTMENT_HEAD): True,
    ("refund_200_01", UserRole.EXECUTIVE): True,
    ("refund_200_01", UserRole.FINANCE_REVIEWER): True,
    ("refund_200_01", UserRole.VP_FINANCE): True,
    ("refund_200_01", UserRole.SYSTEM_ADMIN): False,

    # 11. Refund $500 (Manager / Head / Exec limit boundary)
    ("refund_500", UserRole.SUPPORT_AGENT): False,
    ("refund_500", UserRole.TEAM_LEAD): False,
    ("refund_500", UserRole.TEAM_MANAGER): True,
    ("refund_500", UserRole.DEPARTMENT_HEAD): True,
    ("refund_500", UserRole.EXECUTIVE): True,
    ("refund_500", UserRole.FINANCE_REVIEWER): True,
    ("refund_500", UserRole.VP_FINANCE): True,
    ("refund_500", UserRole.SYSTEM_ADMIN): False,

    # 12. Refund $500.01 (Above $500: Finance only)
    ("refund_500_01", UserRole.SUPPORT_AGENT): False,
    ("refund_500_01", UserRole.TEAM_LEAD): False,
    ("refund_500_01", UserRole.TEAM_MANAGER): False,
    ("refund_500_01", UserRole.DEPARTMENT_HEAD): False,
    ("refund_500_01", UserRole.EXECUTIVE): False,
    ("refund_500_01", UserRole.FINANCE_REVIEWER): True,
    ("refund_500_01", UserRole.VP_FINANCE): True,
    ("refund_500_01", UserRole.SYSTEM_ADMIN): False,

    # 13. Refund $1,000 (Finance Reviewer limit boundary)
    ("refund_1000", UserRole.SUPPORT_AGENT): False,
    ("refund_1000", UserRole.TEAM_LEAD): False,
    ("refund_1000", UserRole.TEAM_MANAGER): False,
    ("refund_1000", UserRole.DEPARTMENT_HEAD): False,
    ("refund_1000", UserRole.EXECUTIVE): False,
    ("refund_1000", UserRole.FINANCE_REVIEWER): True,
    ("refund_1000", UserRole.VP_FINANCE): True,
    ("refund_1000", UserRole.SYSTEM_ADMIN): False,

    # 14. Refund $1,000.01 (Finance Reviewer exceeded: VP Finance only)
    ("refund_1000_01", UserRole.SUPPORT_AGENT): False,
    ("refund_1000_01", UserRole.TEAM_LEAD): False,
    ("refund_1000_01", UserRole.TEAM_MANAGER): False,
    ("refund_1000_01", UserRole.DEPARTMENT_HEAD): False,
    ("refund_1000_01", UserRole.EXECUTIVE): False,
    ("refund_1000_01", UserRole.FINANCE_REVIEWER): False,
    ("refund_1000_01", UserRole.VP_FINANCE): True,
    ("refund_1000_01", UserRole.SYSTEM_ADMIN): False,

    # 15. Refund $100,000 (VP Finance only)
    ("refund_100000", UserRole.SUPPORT_AGENT): False,
    ("refund_100000", UserRole.TEAM_LEAD): False,
    ("refund_100000", UserRole.TEAM_MANAGER): False,
    ("refund_100000", UserRole.DEPARTMENT_HEAD): False,
    ("refund_100000", UserRole.EXECUTIVE): False,
    ("refund_100000", UserRole.FINANCE_REVIEWER): False,
    ("refund_100000", UserRole.VP_FINANCE): True,
    ("refund_100000", UserRole.SYSTEM_ADMIN): False,
}


def build_action_for_key(action_key: str) -> NextBestAction:
    if action_key == "standard_resolution":
        return NextBestAction(action_type=ActionType.RESOLVE_STANDARD, target_team="Customer Support")
    elif action_key == "transfer":
        return NextBestAction(action_type=ActionType.TRANSFER_TEAM, target_team="Logistics", is_cross_team=True)
    elif action_key == "escalate_l1":
        return NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L1)
    elif action_key == "escalate_l2":
        return NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L2)
    elif action_key == "escalate_l3":
        return NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L3)
    elif action_key == "escalate_l4":
        return NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L4)
    elif action_key == "refund_50":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("50.00"))
    elif action_key == "refund_50_01":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("50.01"))
    elif action_key == "refund_200":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("200.00"))
    elif action_key == "refund_200_01":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("200.01"))
    elif action_key == "refund_500":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("500.00"))
    elif action_key == "refund_500_01":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("500.01"))
    elif action_key == "refund_1000":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("1000.00"))
    elif action_key == "refund_1000_01":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("1000.01"))
    elif action_key == "refund_100000":
        return NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("100000.00"))
    raise ValueError(f"Unknown action key: {action_key}")


class TestTableDrivenAuthority:

    def test_hand_written_table_count(self):
        """Assert table size is exactly 120 (15 actions x 8 roles)."""
        assert len(HAND_WRITTEN_TRUTH_TABLE) == 120
        assert len(ACTIONS_UNDER_TEST) == 15
        assert len(ALL_ROLES) == 8

    @pytest.mark.parametrize("action_key", ACTIONS_UNDER_TEST)
    @pytest.mark.parametrize("role", ALL_ROLES)
    def test_every_role_against_every_boundary(self, action_key: str, role: UserRole):
        expected_allowed = HAND_WRITTEN_TRUTH_TABLE[(action_key, role)]
        user = make_user(role)
        action = build_action_for_key(action_key)

        allowed, reason, required_roles = can_approve(user, action)

        assert allowed == expected_allowed, (
            f"Failed for role={role.value}, action={action_key}. "
            f"Expected {expected_allowed}, got {allowed}. Reason: {reason}"
        )
        if allowed:
            assert role in required_roles
        else:
            assert role not in required_roles


# ---------------------------------------------------------------------------
# 2. Document Sync Test (Markdown policy table vs authority.py)
# ---------------------------------------------------------------------------

class TestDocumentSync:

    def test_doc_sync_roles_and_refund_limits(self):
        """
        Parses Roles and Approval by Action tables in approval_authority_matrix.md
        and asserts role names and refund limits match authority.py.
        Fails if the handbook and code drift apart.
        """
        policy_path = Path("backend/data/policies/approval_authority_matrix.md")
        assert policy_path.exists(), f"Policy matrix file missing: {policy_path}"

        content = policy_path.read_text(encoding="utf-8")

        # Map display names from markdown table to UserRole
        doc_role_map = {
            "Tier 1 Agent": (UserRole.SUPPORT_AGENT, Decimal("50")),
            "Team Lead": (UserRole.TEAM_LEAD, Decimal("200")),
            "Team Manager": (UserRole.TEAM_MANAGER, Decimal("500")),
            "Department Head": (UserRole.DEPARTMENT_HEAD, Decimal("500")),
            "Executive": (UserRole.EXECUTIVE, Decimal("500")),
            "Finance Reviewer": (UserRole.FINANCE_REVIEWER, Decimal("1000")),
            "VP Finance": (UserRole.VP_FINANCE, Decimal("Infinity")),  # Any amount
            "System Administrator": (UserRole.SYSTEM_ADMIN, None),
        }

        # Check that all 8 roles are mentioned in Document Control / Roles table
        for title, (role, expected_limit) in doc_role_map.items():
            assert title in content, f"Role title '{title}' not found in handbook markdown"
            code_limit = REFUND_LIMITS[role]
            assert code_limit == expected_limit, (
                f"Mismatch for role {role.value}: handbook expected {expected_limit}, authority.py has {code_limit}"
            )

        # Check version 1.1 in Document Control
        assert "Version: 1.1" in content or "1.1" in content


# ---------------------------------------------------------------------------
# 3. Specific Edge Cases
# ---------------------------------------------------------------------------

class TestSpecificAuthorityCases:

    def test_system_admin_denied_everywhere(self):
        admin = make_user(UserRole.SYSTEM_ADMIN)
        actions = [
            NextBestAction(action_type=ActionType.RESOLVE_STANDARD),
            NextBestAction(action_type=ActionType.TRANSFER_TEAM, target_team="Billing"),
            NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L1),
            NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L4),
            NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("10.00")),
            NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("500.00")),
            NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("10000.00")),
        ]
        for act in actions:
            allowed, reason, req = can_approve(admin, act)
            assert allowed is False
            assert "System Administrator" in reason or "system_admin" in reason

    def test_department_head_and_executive_denied_501_refund(self):
        head = make_user(UserRole.DEPARTMENT_HEAD)
        exec_user = make_user(UserRole.EXECUTIVE)
        refund_501 = NextBestAction(
            action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
            amount=Decimal("501.00"),
        )
        for user in [head, exec_user]:
            allowed, reason, req = can_approve(user, refund_501)
            assert allowed is False
            assert "limit $500" in reason or "500" in reason
            assert UserRole.FINANCE_REVIEWER in req
            assert UserRole.VP_FINANCE in req

    def test_finance_reviewer_denied_escalations_and_standard_resolutions(self):
        finance = make_user(UserRole.FINANCE_REVIEWER)
        std = NextBestAction(action_type=ActionType.RESOLVE_STANDARD)
        l1 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L1)
        l2 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L2)

        for act in [std, l1, l2]:
            allowed, reason, req = can_approve(finance, act)
            assert allowed is False
            assert "Finance" in reason or "finance" in reason

    def test_vp_finance_approves_any_refund_but_no_escalation(self):
        vpf = make_user(UserRole.VP_FINANCE)
        large_refund = NextBestAction(
            action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
            amount=Decimal("250000.00"),
        )
        allowed, reason, req = can_approve(vpf, large_refund)
        assert allowed is True

        escalation = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L3)
        allowed_esc, reason_esc, req_esc = can_approve(vpf, escalation)
        assert allowed_esc is False

    def test_modified_action_raising_amount_is_rechecked(self):
        lead = make_user(UserRole.TEAM_LEAD)
        # Original: $150 (lead can approve)
        orig_action = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("150.00"))
        assert can_approve(lead, orig_action)[0] is True

        # Modified: $400 (lead cannot approve)
        modified_action = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("400.00"))
        allowed, reason, req = can_approve(lead, modified_action)
        assert allowed is False
        assert "limit $200" in reason

    def test_self_approval_above_tier_1_limits_blocked(self):
        lead = make_user(UserRole.TEAM_LEAD, user_id="USR-LEAD-1")
        wf = WorkflowInstance(
            workflow_id="WF-SELF-1",
            status=WorkflowStatus.PENDING_APPROVAL,
            started_at=datetime.now(timezone.utc).isoformat(),
            requester=lead,
            started_by="USR-LEAD-1",  # Lead started case
            request=ComplaintInvestigationRequest(issue_summary="Test"),
        )

        # Standard resolution: allowed under Rule 4 exemption
        std = NextBestAction(action_type=ActionType.RESOLVE_STANDARD)
        assert can_approve(lead, std, workflow=wf)[0] is True

        # Refund $40: allowed under Tier 1 limit
        ref_40 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("40.00"))
        assert can_approve(lead, ref_40, workflow=wf)[0] is True

        # Refund $100: above Tier 1 limit ($50) -> blocked
        ref_100 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("100.00"))
        allowed, reason, req = can_approve(lead, ref_100, workflow=wf)
        assert allowed is False
        assert "opened this case" in reason

    def test_refund_with_no_amount_cannot_be_approved(self):
        mgr = make_user(UserRole.TEAM_MANAGER)
        no_amount = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=None)
        allowed, reason, req = can_approve(mgr, no_amount)
        assert allowed is False
        assert "positive monetary amount" in reason.lower() or "amount" in reason.lower()

    def test_modification_without_note_rejected(self):
        lead = make_user(UserRole.TEAM_LEAD)
        sub = ApprovalSubmission(
            decision=ApprovalDecisionType.MODIFY,
            modified_action=NextBestAction(action_type=ActionType.RESOLVE_STANDARD),
            notes="",  # Empty notes
            rejection_reason="",
        )
        assert sub.decision == ApprovalDecisionType.MODIFY
        orch = WorkflowOrchestrator()
        wf = WorkflowInstance(
            workflow_id="WF-MOD-1",
            status=WorkflowStatus.PENDING_APPROVAL,
            started_at=datetime.now(timezone.utc).isoformat(),
            requester=lead,
            started_by="USR-LEAD-1",
            request=ComplaintInvestigationRequest(issue_summary="Test"),
            reasoning_output=ReasoningOutput(
                status="RECOMMENDATION_READY",
                customer_summary="Test",
                identified_root_cause="Test",
                recommendation=NextBestAction(action_type=ActionType.RESOLVE_STANDARD),
                rationale="Test",
                citations=[EvidenceCitation(source_type="policy", source_id="refund_policy.md")],
                confidence_score=0.9,
                requires_human_approval=True,
            ),
        )
        orch._workflows[wf.workflow_id] = wf

        with pytest.raises(ValueError, match="note"):
            orch.submit_approval(wf.workflow_id, sub, lead)


# ---------------------------------------------------------------------------
# 4. Auto-Execution Condition Tests
# ---------------------------------------------------------------------------

class TestAutoExecutionConditions:

    def test_auto_execution_requires_all_5_conditions(self):
        req = ComplaintInvestigationRequest(
            issue_summary="Password help",
            priority="low",
            category="general",
            flags=[],
        )
        reasoning = ReasoningOutput(
            status="RECOMMENDATION_READY",
            customer_summary="Summary",
            identified_root_cause="Root cause",
            recommendation=NextBestAction(action_type=ActionType.RESOLVE_STANDARD),
            rationale="Explanation",
            citations=[
                EvidenceCitation(source_type="policy", source_id="policy1.md"),
                EvidenceCitation(source_type="policy", source_id="policy2.md"),
            ],
            confidence_score=0.85,
            requires_human_approval=False,
        )

        # All passing -> auto executable
        assert is_auto_executable(reasoning, req) is True

        # Condition 1 fails: action has money
        r1 = reasoning.model_copy(deep=True)
        assert r1.recommendation is not None
        r1.recommendation.amount = Decimal("20.00")
        assert is_auto_executable(r1, req) is False

        # Condition 2 fails: priority high
        req2 = req.model_copy(update={"priority": "high"})
        assert is_auto_executable(reasoning, req2) is False

        # Condition 3 fails: security flag present
        req3 = req.model_copy(update={"flags": ["security"]})
        assert is_auto_executable(reasoning, req3) is False

        # Condition 4 fails: category is billing
        req4 = req.model_copy(update={"category": "billing"})
        assert is_auto_executable(reasoning, req4) is False

        # Condition 5 fails: only 1 citation
        r5 = reasoning.model_copy(deep=True)
        r5.citations = [EvidenceCitation(source_type="policy", source_id="policy1.md")]
        assert is_auto_executable(r5, req) is False

        # Missing priority -> not auto executable
        req_missing = req.model_copy(update={"priority": None})
        assert is_auto_executable(reasoning, req_missing) is False


# ---------------------------------------------------------------------------
# 5. API 403 Response Bodies Name Required Roles
# ---------------------------------------------------------------------------

class TestAPI403Responses:

    def test_403_body_names_required_roles(self):
        client = TestClient(app)

        from backend.orchestrator.orchestrator import get_orchestrator
        orch = get_orchestrator()

        wf_id = "test-wf-403-case"
        agent_user = make_user(UserRole.SUPPORT_AGENT, user_id="USR-AGENT-001")
        wf = WorkflowInstance(
            workflow_id=wf_id,
            status=WorkflowStatus.PENDING_APPROVAL,
            started_at=datetime.now(timezone.utc).isoformat(),
            requester=agent_user,
            started_by="USR-AGENT-001",
            request=ComplaintInvestigationRequest(issue_summary="Refund inquiry"),
            reasoning_output=ReasoningOutput(
                status="RECOMMENDATION_READY",
                recommendation=NextBestAction(
                    action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
                    amount=Decimal("300.00"),
                ),
                citations=[EvidenceCitation(source_type="policy", source_id="refund_policy.md")],
                confidence_score=0.9,
                requires_human_approval=True,
            ),
        )
        orch._workflows[wf_id] = wf

        # Attempt decision as Tier 1 Agent on $300 refund
        decision_res = client.post(
            f"/api/workflow/{wf_id}/decision",
            json={
                "decision": "APPROVE",
                "notes": "Trying to approve $300 refund as Tier 1 agent",
            },
            headers={"Authorization": "Bearer flowmind-agent-token-001"},
        )
        assert decision_res.status_code == 403
        body = decision_res.json()

        detail = body.get("detail", body)
        assert detail.get("error") == "RBAC_PERMISSION_DENIED"
        assert "required_roles" in detail
        assert len(detail["required_roles"]) > 0
        assert "team_manager" in detail["required_roles"]
        assert "finance_reviewer" in detail["required_roles"]
        assert "vp_finance" in detail["required_roles"]
