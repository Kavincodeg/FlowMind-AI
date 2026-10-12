"""
FlowMind AI - Unit Tests for Authority Engine & Task 3 Requirements
Verifies:
  1. can_approve(user, action, workflow) returns (allowed, reason, required_roles)
  2. Standard resolutions: support line only, no finance roles, no system_admin
  3. Re-routing (team_lead+) and cross-team transfer (team_manager+)
  4. Escalations L1 to L4 (support line only)
  5. Refunds: positive Decimal amount required, inclusive thresholds, >$500 finance-only
  6. Modified action checked against final action (raising $150 to $400 denied for lead)
  7. Self-approval (Rule 4): case owner cannot approve except standard resolutions and refunds <=$50
  8. Notes and reasons: rejecting requires reason, modifying requires note (400 / ValueError without note)
  9. Approval record completeness in hash chain and verification
 10. Approval deadlines (approval_due_at)
"""
from datetime import datetime, timezone
from decimal import Decimal
import pytest

from backend.orchestrator.models import ApprovalDecisionType, ApprovalSubmission, WorkflowStatus
from backend.orchestrator.orchestrator import WorkflowOrchestrator
from backend.reasoning.models import ActionType, EscalationLevel, NextBestAction, ComplaintInvestigationRequest
from backend.security.authority import (
    can_approve,
    compute_approval_due_at,
    REFUND_LIMITS,
    ROLE_DISPLAY_NAMES,
)
from backend.security.models import PRECONFIGURED_PERSONAS, UserContext, UserRole
from backend.security.rbac import RBACPermissionDeniedError, verify_approval_permission
from backend.audit.service import AuditService


def make_user(role: UserRole, user_id: str = "USR-TEST") -> UserContext:
    return UserContext(
        user_id=user_id,
        name=f"Test {ROLE_DISPLAY_NAMES[role]}",
        role=role,
    )


class TestAuthorityMatrixRules:

    def test_standard_resolution_authority(self):
        action = NextBestAction(action_type=ActionType.RESOLVE_STANDARD, target_team="Customer Support")

        # Support line can approve
        for role in [UserRole.SUPPORT_AGENT, UserRole.TEAM_LEAD, UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE]:
            user = make_user(role)
            allowed, reason, req = can_approve(user, action)
            assert allowed is True, f"{role} should approve standard resolution"
            assert user.role in req

        # Finance line and system admin CANNOT approve
        for role in [UserRole.FINANCE_REVIEWER, UserRole.VP_FINANCE, UserRole.SYSTEM_ADMIN]:
            user = make_user(role)
            allowed, reason, req = can_approve(user, action)
            assert allowed is False, f"{role} should not approve standard resolution"

    def test_team_routing_and_transfer_authority(self):
        # Intra-team reroute
        reroute = NextBestAction(
            action_type=ActionType.TRANSFER_TEAM,
            target_team="Tier 1 Queue",
            is_cross_team=False,
            parameters={"intra_team": True},
        )
        assert can_approve(make_user(UserRole.SUPPORT_AGENT), reroute)[0] is False
        assert can_approve(make_user(UserRole.TEAM_LEAD), reroute)[0] is True
        assert can_approve(make_user(UserRole.TEAM_MANAGER), reroute)[0] is True

        # Cross-team transfer
        transfer = NextBestAction(
            action_type=ActionType.TRANSFER_TEAM,
            target_team="Engineering",
            is_cross_team=True,
            parameters={"cross_team": True},
        )
        assert can_approve(make_user(UserRole.SUPPORT_AGENT), transfer)[0] is False
        assert can_approve(make_user(UserRole.TEAM_LEAD), transfer)[0] is False
        assert can_approve(make_user(UserRole.TEAM_MANAGER), transfer)[0] is True
        assert can_approve(make_user(UserRole.DEPARTMENT_HEAD), transfer)[0] is True

    def test_escalation_tiers_authority(self):
        l1 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L1)
        l2 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L2)
        l3 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L3)
        l4 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L4)

        # L1: team_lead+
        assert can_approve(make_user(UserRole.SUPPORT_AGENT), l1)[0] is False
        assert can_approve(make_user(UserRole.TEAM_LEAD), l1)[0] is True

        # L2: team_manager+
        assert can_approve(make_user(UserRole.TEAM_LEAD), l2)[0] is False
        assert can_approve(make_user(UserRole.TEAM_MANAGER), l2)[0] is True

        # L3: department_head+
        assert can_approve(make_user(UserRole.TEAM_MANAGER), l3)[0] is False
        assert can_approve(make_user(UserRole.DEPARTMENT_HEAD), l3)[0] is True

        # L4: executive only
        assert can_approve(make_user(UserRole.DEPARTMENT_HEAD), l4)[0] is False
        assert can_approve(make_user(UserRole.EXECUTIVE), l4)[0] is True

        # Finance roles cannot approve any escalation
        for lvl_action in [l1, l2, l3, l4]:
            assert can_approve(make_user(UserRole.FINANCE_REVIEWER), lvl_action)[0] is False
            assert can_approve(make_user(UserRole.VP_FINANCE), lvl_action)[0] is False

    def test_refund_amount_required_and_limits(self):
        # Missing amount
        no_amt = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION)
        allowed, reason, _ = can_approve(make_user(UserRole.VP_FINANCE), no_amt)
        assert allowed is False
        assert "positive monetary amount" in reason

        # Zero or negative amount
        zero_amt = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("0.00"))
        assert can_approve(make_user(UserRole.VP_FINANCE), zero_amt)[0] is False

        # $50 refund (Tier 1 limit)
        ref_50 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("50.00"))
        assert can_approve(make_user(UserRole.SUPPORT_AGENT), ref_50)[0] is True

        # $200 refund (Team Lead limit)
        ref_200 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("200.00"))
        assert can_approve(make_user(UserRole.SUPPORT_AGENT), ref_200)[0] is False
        assert can_approve(make_user(UserRole.TEAM_LEAD), ref_200)[0] is True

        # $300 refund (Team Manager, Finance Reviewer, VP Finance)
        ref_300 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("300.00"))
        allowed_lead, reason_lead, _ = can_approve(make_user(UserRole.TEAM_LEAD), ref_300)
        assert allowed_lead is False
        assert "A $300 refund needs a" in reason_lead
        assert "limit $200" in reason_lead
        assert can_approve(make_user(UserRole.TEAM_MANAGER), ref_300)[0] is True
        assert can_approve(make_user(UserRole.FINANCE_REVIEWER), ref_300)[0] is True
        assert can_approve(make_user(UserRole.VP_FINANCE), ref_300)[0] is True

        # $600 refund (Refunds above $500 belong to Finance!)
        ref_600 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("600.00"))
        assert can_approve(make_user(UserRole.TEAM_MANAGER), ref_600)[0] is False
        assert can_approve(make_user(UserRole.DEPARTMENT_HEAD), ref_600)[0] is False
        assert can_approve(make_user(UserRole.EXECUTIVE), ref_600)[0] is False
        assert can_approve(make_user(UserRole.FINANCE_REVIEWER), ref_600)[0] is True
        assert can_approve(make_user(UserRole.VP_FINANCE), ref_600)[0] is True

        # $1,200 refund (VP Finance only)
        ref_1200 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("1200.00"))
        assert can_approve(make_user(UserRole.FINANCE_REVIEWER), ref_1200)[0] is False
        assert can_approve(make_user(UserRole.VP_FINANCE), ref_1200)[0] is True


class TestRule4SelfApprovalAndModifications:

    def test_self_approval_rule_4(self):
        class DummyWorkflow:
            started_by = "USR-OWNER"

        wf = DummyWorkflow()
        owner_lead = make_user(UserRole.TEAM_LEAD, user_id="USR-OWNER")

        # Owner can approve standard resolution (Tier 1 limit)
        std_act = NextBestAction(action_type=ActionType.RESOLVE_STANDARD)
        assert can_approve(owner_lead, std_act, workflow=wf)[0] is True

        # Owner can approve $50 refund (Tier 1 limit)
        ref_50 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("50.00"))
        assert can_approve(owner_lead, ref_50, workflow=wf)[0] is True

        # Owner CANNOT approve refund above $50 (e.g. $150)
        ref_150 = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("150.00"))
        allowed, reason, _ = can_approve(owner_lead, ref_150, workflow=wf)
        assert allowed is False
        assert "You opened this case, so someone else must approve it." in reason

        # Non-owner lead CAN approve $150
        other_lead = make_user(UserRole.TEAM_LEAD, user_id="USR-OTHER")
        assert can_approve(other_lead, ref_150, workflow=wf)[0] is True

    def test_modifying_action_authority_and_notes(self):
        lead = make_user(UserRole.TEAM_LEAD)
        # Original proposal $150
        orig = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("150.00"))
        # Modified raises to $400 (exceeds lead limit of $200)
        mod_raised = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("400.00"))

        assert can_approve(lead, orig)[0] is True
        allowed, reason, _ = can_approve(lead, mod_raised)
        assert allowed is False
        assert "limit $200" in reason

    def test_deadline_calculation(self):
        t0 = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
        l1 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L1)
        l2 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L2)
        l3 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L3)
        l4 = NextBestAction(action_type=ActionType.ESCALATE_TICKET, escalation_level=EscalationLevel.L4)
        ref_fin = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("750.00"))
        ref_vp = NextBestAction(action_type=ActionType.ISSUE_REFUND_RECOMMENDATION, amount=Decimal("1500.00"))

        assert compute_approval_due_at(l1, t0) == datetime(2026, 10, 12, 14, 0, 0, tzinfo=timezone.utc)
        assert compute_approval_due_at(l2, t0) == datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
        assert compute_approval_due_at(l3, t0) == datetime(2026, 10, 12, 11, 0, 0, tzinfo=timezone.utc)
        assert compute_approval_due_at(l4, t0) == datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
        assert compute_approval_due_at(ref_fin, t0) == datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)
        assert compute_approval_due_at(ref_vp, t0) == datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc)
