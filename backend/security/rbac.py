"""
FlowMind AI - Role-Based Access Control (RBAC) Engine (Phase 3)
Enforces strict role permissions for investigating complaints and approving actions.
RBAC IS REAL, NOT COSMETIC: Unauthorized users cannot approve actions beyond their tier.
"""
from __future__ import annotations

import logging
from typing import Optional, Set, Tuple

from backend.reasoning.models import ActionType, EscalationLevel, NextBestAction
from backend.security.models import UserContext, UserRole

logger = logging.getLogger(__name__)


class RBACPermissionDeniedError(PermissionError):
    """Raised when an authenticated user lacks sufficient authority to approve an action."""

    def __init__(
        self,
        user: UserContext,
        action: NextBestAction,
        reason: str,
    ):
        self.user_id = user.user_id
        self.user_role = user.role
        self.action_type = action.action_type
        self.escalation_level = action.escalation_level
        self.reason = reason
        super().__init__(
            f"RBAC Permission Denied: User '{user.name}' ({user.user_id}) with role '{user.role.value}' "
            f"is not authorized to approve action '{action.action_type.value}' "
            f"(tier={action.escalation_level.value if action.escalation_level else 'N/A'}). Reason: {reason}"
        )


def can_approve_action(user: UserContext, action: NextBestAction) -> Tuple[bool, str]:
    """
    Evaluates whether a user's verified role grants authority to approve an action proposal.
    Returns (is_authorized, explanation).
    """
    if user.role == UserRole.SYSTEM_ADMIN:
        return False, "System Administrator has no approval authority."

    # 1. Standard Resolutions & Customer Info Requests
    if action.action_type in (ActionType.RESOLVE_STANDARD, ActionType.REQUEST_CUSTOMER_INFO, ActionType.NO_ACTION):
        if user.role in (UserRole.SUPPORT_AGENT, UserRole.TEAM_LEAD, UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE):
            return True, f"Role '{user.role.value}' is authorized to approve standard resolutions."
        return False, f"Role '{user.role.value}' cannot approve standard resolutions."

    # 2. Team Transfer Routing
    if action.action_type == ActionType.TRANSFER_TEAM:
        if user.role in (UserRole.TEAM_LEAD, UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE):
            return True, f"Role '{user.role.value}' is authorized to approve team transfers."
        return False, f"Role '{user.role.value}' cannot approve team transfers. Requires Team Lead or above."

    # 3. Financial Refunds
    if action.action_type == ActionType.ISSUE_REFUND_RECOMMENDATION:
        if user.role in (UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE, UserRole.FINANCE_REVIEWER, UserRole.VP_FINANCE):
            return True, f"Role '{user.role.value}' may approve refunds within their threshold."
        return False, f"Role '{user.role.value}' cannot approve financial refunds. Requires Manager or above."

    # 4. Ticket Escalations (Tiered by EscalationLevel)
    if action.action_type == ActionType.ESCALATE_TICKET:
        level = action.escalation_level or EscalationLevel.L1
        if level == EscalationLevel.L1:
            if user.role in (UserRole.TEAM_LEAD, UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE):
                return True, f"Role '{user.role.value}' is authorized to approve L1 escalations."
        elif level == EscalationLevel.L2:
            if user.role in (UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE):
                return True, f"Role '{user.role.value}' is authorized to approve L2 escalations."
        elif level == EscalationLevel.L3:
            if user.role in (UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE):
                return True, f"Role '{user.role.value}' is authorized to approve L3 escalations."
        elif level == EscalationLevel.L4:
            if user.role == UserRole.EXECUTIVE:
                return True, f"Role '{user.role.value}' is authorized to approve L4 escalations."
        return False, f"Role '{user.role.value}' cannot approve {level.value} escalations."

    return False, f"Action '{action.action_type.value}' is not permitted for role '{user.role.value}'."


def verify_approval_permission(user: UserContext, action: NextBestAction) -> None:
    """
    Validates user authority for an action proposal; raises RBACPermissionDeniedError on denial.
    CRITICAL: In modification flows, callers must pass the final MODIFIED action to this function.
    """
    allowed, reason = can_approve_action(user, action)
    if not allowed:
        logger.warning(
            "RBAC violation: User %s (%s) denied approval on %s: %s",
            user.user_id,
            user.role.value,
            action.action_type.value,
            reason,
        )
        raise RBACPermissionDeniedError(user=user, action=action, reason=reason)
