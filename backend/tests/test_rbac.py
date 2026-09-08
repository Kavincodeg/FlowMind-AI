"""
FlowMind AI - Tests for Security & RBAC Module (Phase 3)
Verifies:
  1. Complete RBAC permissions matrix across all roles and escalation levels.
  2. RBAC validation on MODIFIED actions (Fix 1).
  3. Server-side token resolution trust boundary (Critical Fix).
"""
import pytest

from backend.reasoning.models import ActionType, EscalationLevel, NextBestAction
from backend.security.auth import resolve_user_from_token
from backend.security.models import PRECONFIGURED_PERSONAS, UserContext, UserRole
from backend.security.rbac import (
    RBACPermissionDeniedError,
    can_approve_action,
    verify_approval_permission,
)


def make_test_user(role: UserRole) -> UserContext:
    return UserContext(
        user_id=f"TEST-{role.value.upper()}",
        name=f"Test {role.value.title()}",
        role=role,
    )


def make_action(
    action_type: ActionType,
    level: EscalationLevel = None,
    urgency: str = "medium",
) -> NextBestAction:
    return NextBestAction(
        action_type=action_type,
        target_team="Test Team",
        escalation_level=level,
        urgency=urgency,
        requires_approval=True,
    )


class TestRBACPermissionsMatrix:
    """Validate permission boundaries across all 4 roles."""

    def test_support_agent_permissions(self):
        agent = make_test_user(UserRole.SUPPORT_AGENT)

        # Allowed: Standard resolution and info requests
        assert can_approve_action(agent, make_action(ActionType.RESOLVE_STANDARD))[0] is True
        assert can_approve_action(agent, make_action(ActionType.REQUEST_CUSTOMER_INFO))[0] is True

        # Denied: Cross-team transfer
        allowed, reason = can_approve_action(agent, make_action(ActionType.TRANSFER_TEAM))
        assert allowed is False
        assert "Team Lead or above" in reason

        # Denied: Any escalation tier
        assert can_approve_action(agent, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L1))[0] is False
        assert can_approve_action(agent, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L2))[0] is False
        assert can_approve_action(agent, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L3))[0] is False

        # Denied: Financial refund
        allowed, reason = can_approve_action(agent, make_action(ActionType.ISSUE_REFUND_RECOMMENDATION))
        assert allowed is False
        assert "Manager or above" in reason

    def test_team_lead_permissions(self):
        lead = make_test_user(UserRole.TEAM_LEAD)

        # Allowed: Standard resolution, team transfer, and L1 escalations
        assert can_approve_action(lead, make_action(ActionType.RESOLVE_STANDARD))[0] is True
        assert can_approve_action(lead, make_action(ActionType.TRANSFER_TEAM))[0] is True
        assert can_approve_action(lead, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L1))[0] is True

        # Denied: L2 and L3 escalations
        allowed_l2, _ = can_approve_action(lead, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L2))
        allowed_l3, _ = can_approve_action(lead, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L3))
        assert allowed_l2 is False
        assert allowed_l3 is False

        # Denied: Financial refund
        assert can_approve_action(lead, make_action(ActionType.ISSUE_REFUND_RECOMMENDATION))[0] is False

    def test_manager_permissions(self):
        manager = make_test_user(UserRole.MANAGER)

        # Allowed: Standard, transfer, refund, L1, L2, L3 escalations
        assert can_approve_action(manager, make_action(ActionType.RESOLVE_STANDARD))[0] is True
        assert can_approve_action(manager, make_action(ActionType.TRANSFER_TEAM))[0] is True
        assert can_approve_action(manager, make_action(ActionType.ISSUE_REFUND_RECOMMENDATION))[0] is True
        assert can_approve_action(manager, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L1))[0] is True
        assert can_approve_action(manager, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L2))[0] is True
        assert can_approve_action(manager, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L3))[0] is True

        # Denied: L4 executive escalation
        allowed_l4, reason = can_approve_action(manager, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L4))
        assert allowed_l4 is False
        assert "Requires Admin role" in reason

    def test_admin_universal_permissions(self):
        admin = make_test_user(UserRole.ADMIN)

        # Universal authorization across all actions and tiers
        assert can_approve_action(admin, make_action(ActionType.RESOLVE_STANDARD))[0] is True
        assert can_approve_action(admin, make_action(ActionType.TRANSFER_TEAM))[0] is True
        assert can_approve_action(admin, make_action(ActionType.ISSUE_REFUND_RECOMMENDATION))[0] is True
        assert can_approve_action(admin, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L1))[0] is True
        assert can_approve_action(admin, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L2))[0] is True
        assert can_approve_action(admin, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L3))[0] is True
        assert can_approve_action(admin, make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L4))[0] is True


class TestRBACEnforcementAndModifications:
    """Validate exceptions and modified action validation (Fix 1)."""

    def test_verify_approval_permission_raises_exception_on_denial(self):
        agent = make_test_user(UserRole.SUPPORT_AGENT)
        action = make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L2)

        with pytest.raises(RBACPermissionDeniedError) as exc_info:
            verify_approval_permission(agent, action)

        err = exc_info.value
        assert err.user_role == UserRole.SUPPORT_AGENT
        assert err.action_type == ActionType.ESCALATE_TICKET
        assert err.escalation_level == EscalationLevel.L2

    def test_fix_1_modified_action_rbac_validation(self):
        """
        Fix 1 Test: When an approver submits decision=MODIFY, verify_approval_permission
        must validate the MODIFIED action, not the original proposal.
        """
        lead = make_test_user(UserRole.TEAM_LEAD)

        # Original proposal is L1 (which lead CAN approve)
        original_action = make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L1)
        assert can_approve_action(lead, original_action)[0] is True

        # Lead attempts to modify into L3 escalation (which lead CANNOT approve)
        modified_action = make_action(ActionType.ESCALATE_TICKET, EscalationLevel.L3)

        # Validating the modified action must raise RBACPermissionDeniedError
        with pytest.raises(RBACPermissionDeniedError) as exc_info:
            verify_approval_permission(lead, modified_action)

        assert "Requires Manager or Admin" in exc_info.value.reason


class TestRBACTrustBoundary:
    """Validate server-side token resolution (Critical Fix)."""

    def test_token_resolution_maps_to_canonical_persona(self):
        # Preconfigured persona tokens map correctly
        user = resolve_user_from_token("flowmind-mgr-token-003")
        assert user is not None
        assert user.name == "Elena Rostova"
        assert user.role == UserRole.MANAGER

        # Invalid or forged token returns None
        assert resolve_user_from_token("forged-admin-token") is None
        assert resolve_user_from_token("") is None
        assert resolve_user_from_token(None) is None
