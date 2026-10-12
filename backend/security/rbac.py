"""
FlowMind AI - Role-Based Access Control (RBAC) Engine (Phase 3 & 4)
Enforces strict role permissions for investigating complaints and approving actions.
Delegates to backend.security.authority for matrix data rules and boundaries.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from backend.reasoning.models import ActionType, EscalationLevel, NextBestAction
from backend.security.authority import can_approve
from backend.security.models import UserContext, UserRole

logger = logging.getLogger(__name__)


class RBACPermissionDeniedError(PermissionError):
    """Raised when an authenticated user lacks sufficient authority to approve an action."""

    def __init__(
        self,
        user: UserContext,
        action: NextBestAction,
        reason: str,
        required_roles: Optional[List[UserRole]] = None,
    ):
        self.user_id = user.user_id
        self.user_role = user.role
        self.action_type = action.action_type
        self.escalation_level = action.escalation_level
        self.reason = reason
        self.required_roles = required_roles or []
        super().__init__(
            f"RBAC Permission Denied: User '{user.name}' ({user.user_id}) with role '{user.role.value}' "
            f"is not authorized to approve action '{action.action_type.value}'. Reason: {reason}"
        )


def can_approve_action(
    user: UserContext,
    action: NextBestAction,
    workflow: Optional[Any] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether a user's verified role grants authority to approve an action proposal.
    Returns (is_authorized, explanation).
    """
    allowed, reason, _ = can_approve(user, action, workflow=workflow)
    return allowed, reason


def verify_approval_permission(
    user: UserContext,
    action: NextBestAction,
    workflow: Optional[Any] = None,
) -> None:
    """
    Validates user authority for an action proposal; raises RBACPermissionDeniedError on denial.
    CRITICAL: In modification flows, callers must pass the final MODIFIED action to this function.
    """
    allowed, reason, required_roles = can_approve(user, action, workflow=workflow)
    if not allowed:
        logger.warning(
            "RBAC violation: User %s (%s) denied approval on %s: %s",
            user.user_id,
            user.role.value,
            action.action_type.value,
            reason,
        )
        raise RBACPermissionDeniedError(
            user=user,
            action=action,
            reason=reason,
            required_roles=required_roles,
        )
