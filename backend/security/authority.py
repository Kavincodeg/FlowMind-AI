"""
FlowMind AI - Approval Authority Matrix Engine (Phase 4 / Prompt 3)
Single machine-readable source of truth for approval authority and response deadlines.
Implements the rules from approval_authority_matrix.md and customer_query_handling_policy.md.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.reasoning.models import ActionType, EscalationLevel, NextBestAction
from backend.security.models import UserContext, UserRole

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Human-readable role display names (from matrix "Roles" table)
# ---------------------------------------------------------------------------
ROLE_DISPLAY_NAMES: Dict[UserRole, str] = {
    UserRole.SUPPORT_AGENT: "Tier 1 Agent",
    UserRole.TEAM_LEAD: "Team Lead",
    UserRole.TEAM_MANAGER: "Team Manager",
    UserRole.DEPARTMENT_HEAD: "Department Head",
    UserRole.EXECUTIVE: "Executive",
    UserRole.FINANCE_REVIEWER: "Finance Reviewer",
    UserRole.VP_FINANCE: "VP Finance",
    UserRole.SYSTEM_ADMIN: "System Administrator",
}

# ---------------------------------------------------------------------------
# 2. Role lines / hierarchies as data
# ---------------------------------------------------------------------------
SUPPORT_LINE_ROLES: List[UserRole] = [
    UserRole.SUPPORT_AGENT,
    UserRole.TEAM_LEAD,
    UserRole.TEAM_MANAGER,
    UserRole.DEPARTMENT_HEAD,
    UserRole.EXECUTIVE,
]

FINANCE_LINE_ROLES: List[UserRole] = [
    UserRole.FINANCE_REVIEWER,
    UserRole.VP_FINANCE,
]

# ---------------------------------------------------------------------------
# 3. Maximum refund limits per role (inclusive)
# ---------------------------------------------------------------------------
# Handbook Rule 3: "Refunds above $500 belong to Finance. Support leadership
# cannot approve them, whatever their level."
REFUND_LIMITS: Dict[UserRole, Optional[Decimal]] = {
    UserRole.SUPPORT_AGENT: Decimal("50.00"),
    UserRole.TEAM_LEAD: Decimal("200.00"),
    UserRole.TEAM_MANAGER: Decimal("500.00"),
    UserRole.DEPARTMENT_HEAD: Decimal("500.00"),
    UserRole.EXECUTIVE: Decimal("500.00"),
    UserRole.FINANCE_REVIEWER: Decimal("1000.00"),
    UserRole.VP_FINANCE: Decimal("Infinity"),
    UserRole.SYSTEM_ADMIN: None,
}

# ---------------------------------------------------------------------------
# 4. Standard action approval mappings as data
# ---------------------------------------------------------------------------
STANDARD_RESOLUTION_ROLES: List[UserRole] = [
    UserRole.SUPPORT_AGENT,
    UserRole.TEAM_LEAD,
    UserRole.TEAM_MANAGER,
    UserRole.DEPARTMENT_HEAD,
    UserRole.EXECUTIVE,
]

REROUTE_WITHIN_TEAM_ROLES: List[UserRole] = [
    UserRole.TEAM_LEAD,
    UserRole.TEAM_MANAGER,
    UserRole.DEPARTMENT_HEAD,
    UserRole.EXECUTIVE,
]

CROSS_TEAM_TRANSFER_ROLES: List[UserRole] = [
    UserRole.TEAM_MANAGER,
    UserRole.DEPARTMENT_HEAD,
    UserRole.EXECUTIVE,
]

ESCALATION_ROLES: Dict[EscalationLevel, List[UserRole]] = {
    EscalationLevel.L1: [
        UserRole.TEAM_LEAD,
        UserRole.TEAM_MANAGER,
        UserRole.DEPARTMENT_HEAD,
        UserRole.EXECUTIVE,
    ],
    EscalationLevel.L2: [
        UserRole.TEAM_MANAGER,
        UserRole.DEPARTMENT_HEAD,
        UserRole.EXECUTIVE,
    ],
    EscalationLevel.L3: [
        UserRole.DEPARTMENT_HEAD,
        UserRole.EXECUTIVE,
    ],
    EscalationLevel.L4: [
        UserRole.EXECUTIVE,
    ],
}

# ---------------------------------------------------------------------------
# 5. Response times for SLA / approval deadlines
# ---------------------------------------------------------------------------
RESPONSE_DURATIONS: Dict[str, timedelta] = {
    "L1": timedelta(hours=4),
    "L2": timedelta(hours=2),
    "L3": timedelta(hours=1),
    "L4": timedelta(seconds=0),
    "finance_reviewer": timedelta(days=1),
    "vp_finance": timedelta(days=2),
    "tier_1": timedelta(hours=4),
}


def parse_decimal_amount(val: Any) -> Optional[Decimal]:
    """Safely parse an amount into a positive Decimal, or return None."""
    if val is None:
        return None
    try:
        d = Decimal(str(val))
        return d if d > Decimal("0") else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def format_role_list(roles: List[UserRole]) -> str:
    """Format role list into natural English (e.g. 'Team Manager, Finance Reviewer or VP Finance')."""
    if not roles:
        return "none"
    names = [ROLE_DISPLAY_NAMES.get(r, r.value) for r in roles]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " or " + names[-1]


def format_currency(val: Decimal) -> str:
    """Format Decimal into clean currency without trailing zeros if integer."""
    if val.is_infinite():
        return "any amount"
    if val == val.to_integral_value():
        return f"${val:,.0f}"
    return f"${val:,.2f}"


def compute_approval_due_at(action: Optional[NextBestAction], started_at: Optional[datetime] = None) -> datetime:
    """
    Calculate approval_due_at based on the required role's response time:
    - Escalation: L1 4h, L2 2h, L3 1h, L4 immediate
    - Refund: >$1,000 (VP Finance) 2 business days; >$500 (Finance Reviewer) 1 business day; <=$500 2h-4h
    - Transfers: 2h (Team Manager)
    - Routine / Tier 1: 4h
    """
    base_time = started_at or datetime.now(timezone.utc)
    if not action:
        return base_time + RESPONSE_DURATIONS["tier_1"]

    if action.action_type == ActionType.ESCALATE_TICKET:
        lvl = action.escalation_level or EscalationLevel.L1
        delta = RESPONSE_DURATIONS.get(lvl.value, timedelta(hours=4))
        return base_time + delta

    if action.action_type == ActionType.ISSUE_REFUND_RECOMMENDATION:
        amt = parse_decimal_amount(action.amount or action.parameters.get("amount"))
        if amt and amt > Decimal("1000.00"):
            return base_time + RESPONSE_DURATIONS["vp_finance"]
        if amt and amt > Decimal("500.00"):
            return base_time + RESPONSE_DURATIONS["finance_reviewer"]
        if amt and amt > Decimal("200.00"):
            return base_time + RESPONSE_DURATIONS["L2"]
        return base_time + RESPONSE_DURATIONS["tier_1"]

    if action.action_type == ActionType.TRANSFER_TEAM:
        return base_time + RESPONSE_DURATIONS["L2"]

    return base_time + RESPONSE_DURATIONS["tier_1"]


def get_required_roles_for_refund(amount: Decimal) -> List[UserRole]:
    """
    Determine exact list of authorized roles for a refund amount:
    - >$500: strictly finance_reviewer (up to $1,000) and vp_finance (any amount)
    - <=$500: support roles whose limit >= amount, plus finance_reviewer ($51-$1000) and vp_finance
    """
    if amount > Decimal("1000.00"):
        return [UserRole.VP_FINANCE]
    if amount > Decimal("500.00"):
        return [UserRole.FINANCE_REVIEWER, UserRole.VP_FINANCE]

    eligible: List[UserRole] = []
    # Support line roles with sufficient limit
    for r in SUPPORT_LINE_ROLES:
        limit = REFUND_LIMITS.get(r)
        if limit is not None and limit >= amount:
            eligible.append(r)

    # Finance Reviewer handles refunds $51 to $1,000
    if amount > Decimal("50.00"):
        eligible.append(UserRole.FINANCE_REVIEWER)

    # VP Finance handles any amount
    eligible.append(UserRole.VP_FINANCE)
    return eligible


def can_approve(
    user: UserContext,
    action: NextBestAction,
    workflow: Optional[Any] = None,
) -> Tuple[bool, str, List[UserRole]]:
    """
    Evaluates approval authority against the Approval Authority Matrix.
    Returns: (allowed: bool, reason: str, required_roles: List[UserRole])
    """
    user_name = ROLE_DISPLAY_NAMES.get(user.role, user.role.value)

    # -----------------------------------------------------------------------
    # Rule 0: System Administrator has no approval authority
    # -----------------------------------------------------------------------
    if user.role == UserRole.SYSTEM_ADMIN:
        req_roles = _get_candidate_roles(action)
        return (
            False,
            "System Administrators have no approval authority.",
            req_roles,
        )

    # -----------------------------------------------------------------------
    # Rule 4: Self-approval check (Document Control Version 1.1)
    # "A person must not approve an action they requested or own, except actions
    # this matrix gives to the Tier 1 Agent (standard resolutions and refunds up to $50)."
    # -----------------------------------------------------------------------
    started_by = None
    if workflow is not None:
        if hasattr(workflow, "started_by") and workflow.started_by:
            started_by = workflow.started_by
        elif hasattr(workflow, "requester") and hasattr(workflow.requester, "user_id"):
            started_by = workflow.requester.user_id

    if started_by and user.user_id == started_by:
        is_tier_1_exempt = False
        if action.action_type in (ActionType.RESOLVE_STANDARD, ActionType.REQUEST_CUSTOMER_INFO, ActionType.NO_ACTION):
            is_tier_1_exempt = True
        elif action.action_type == ActionType.ISSUE_REFUND_RECOMMENDATION:
            amt = parse_decimal_amount(action.amount or action.parameters.get("amount"))
            if amt and amt <= Decimal("50.00"):
                is_tier_1_exempt = True

        if not is_tier_1_exempt:
            req_roles = _get_candidate_roles(action)
            return (
                False,
                "You opened this case, so someone else must approve it.",
                req_roles,
            )

    # -----------------------------------------------------------------------
    # 1. Standard Resolutions & Info Requests
    # -----------------------------------------------------------------------
    if action.action_type in (ActionType.RESOLVE_STANDARD, ActionType.REQUEST_CUSTOMER_INFO, ActionType.NO_ACTION):
        req_roles = STANDARD_RESOLUTION_ROLES
        if user.role in req_roles:
            return True, f"{user_name} is authorized to approve standard resolutions.", req_roles
        return (
            False,
            f"Standard resolution requires a support-line role (Tier 1 Agent to Executive). You are a {user_name}.",
            req_roles,
        )

    # -----------------------------------------------------------------------
    # 2. Team Routing & Cross-Team Transfer
    # -----------------------------------------------------------------------
    if action.action_type == ActionType.TRANSFER_TEAM:
        is_cross_team = getattr(action, "is_cross_team", False) or action.parameters.get("cross_team", False)
        # If parameters specify intra_team / re_route
        if action.parameters.get("intra_team", False) or not is_cross_team:
            # Re-route within team: Team Lead+
            req_roles = REROUTE_WITHIN_TEAM_ROLES
            if user.role in req_roles:
                return True, f"{user_name} is authorized to re-route within the team.", req_roles
            return (
                False,
                f"Re-routing within a team requires a Team Lead or above. You are a {user_name}.",
                req_roles,
            )
        else:
            # Cross-team transfer: Team Manager+
            req_roles = CROSS_TEAM_TRANSFER_ROLES
            if user.role in req_roles:
                return True, f"{user_name} is authorized to approve cross-team transfers.", req_roles
            return (
                False,
                f"Cross-team transfer requires a Team Manager or above. You are a {user_name}.",
                req_roles,
            )

    # -----------------------------------------------------------------------
    # 3. Ticket Escalations (Tiered by EscalationLevel)
    # -----------------------------------------------------------------------
    if action.action_type == ActionType.ESCALATE_TICKET:
        lvl = action.escalation_level or EscalationLevel.L1
        req_roles = ESCALATION_ROLES.get(lvl, [UserRole.EXECUTIVE])
        if user.role in req_roles:
            return True, f"{user_name} is authorized to approve {lvl.value} escalations.", req_roles
        
        req_text = format_role_list(req_roles)
        return (
            False,
            f"An escalation to {lvl.value} needs {req_text}. You are a {user_name}.",
            req_roles,
        )

    # -----------------------------------------------------------------------
    # 4. Financial Refund or Credit
    # -----------------------------------------------------------------------
    if action.action_type == ActionType.ISSUE_REFUND_RECOMMENDATION:
        raw_amt = action.amount if action.amount is not None else action.parameters.get("amount")
        amount = parse_decimal_amount(raw_amt)

        if amount is None:
            return (
                False,
                "A refund recommendation requires a valid positive monetary amount.",
                [],
            )

        req_roles = get_required_roles_for_refund(amount)
        if user.role in req_roles:
            return (
                True,
                f"{user_name} is authorized to approve {format_currency(amount)} refunds.",
                req_roles,
            )

        # Build precise reason stating limits and required roles
        user_limit = REFUND_LIMITS.get(user.role)
        req_text = format_role_list(req_roles)
        amt_text = format_currency(amount)

        if user_limit is not None and not user_limit.is_infinite():
            user_lim_text = format_currency(user_limit)
            reason = f"A {amt_text} refund needs a {req_text}. You are a {user_name} (limit {user_lim_text})."
        else:
            reason = f"A {amt_text} refund needs a {req_text}. You are a {user_name}."

        return False, reason, req_roles

    # Default fallback
    return False, f"Action '{action.action_type.value}' is not recognized in authority matrix.", []


def _get_candidate_roles(action: NextBestAction) -> List[UserRole]:
    """Helper to determine candidate roles for non-authorized roles like system_admin."""
    if action.action_type in (ActionType.RESOLVE_STANDARD, ActionType.REQUEST_CUSTOMER_INFO, ActionType.NO_ACTION):
        return STANDARD_RESOLUTION_ROLES
    if action.action_type == ActionType.TRANSFER_TEAM:
        return CROSS_TEAM_TRANSFER_ROLES
    if action.action_type == ActionType.ESCALATE_TICKET:
        lvl = action.escalation_level or EscalationLevel.L1
        return ESCALATION_ROLES.get(lvl, [UserRole.EXECUTIVE])
    if action.action_type == ActionType.ISSUE_REFUND_RECOMMENDATION:
        amt = parse_decimal_amount(action.amount or action.parameters.get("amount"))
        if amt:
            return get_required_roles_for_refund(amt)
        return [UserRole.SUPPORT_AGENT, UserRole.TEAM_LEAD, UserRole.TEAM_MANAGER]
    return []
