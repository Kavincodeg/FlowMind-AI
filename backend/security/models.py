"""
FlowMind AI - Security & RBAC Models (Phase 3)
Defines user roles, user contexts, and pre-configured personas with authentication tokens.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    """Hierarchical role definitions for enterprise workflows."""
    SUPPORT_AGENT = "support_agent"
    TEAM_LEAD = "team_lead"
    TEAM_MANAGER = "team_manager"
    DEPARTMENT_HEAD = "department_head"
    EXECUTIVE = "executive"
    FINANCE_REVIEWER = "finance_reviewer"
    VP_FINANCE = "vp_finance"
    SYSTEM_ADMIN = "system_admin"


class UserContext(BaseModel):
    """Authenticated user context resolved server-side."""
    model_config = ConfigDict(extra="ignore")

    user_id: str
    name: str
    role: UserRole
    department: str = "Customer Support"
    token: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.SYSTEM_ADMIN

    @property
    def is_manager_or_above(self) -> bool:
        return self.role in (UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE)

    @property
    def is_lead_or_above(self) -> bool:
        return self.role in (UserRole.TEAM_LEAD, UserRole.TEAM_MANAGER, UserRole.DEPARTMENT_HEAD, UserRole.EXECUTIVE)


# Pre-configured test personas with fixed session tokens for API / evaluation
PRECONFIGURED_PERSONAS: Dict[str, UserContext] = {
    "flowmind-agent-token-001": UserContext(
        user_id="USR-001",
        name="Sarah Jenkins",
        role=UserRole.SUPPORT_AGENT,
        department="Tier 1 Support",
        token="flowmind-agent-token-001",
    ),
    "flowmind-lead-token-002": UserContext(
        user_id="USR-002",
        name="Marcus Vance",
        role=UserRole.TEAM_LEAD,
        department="Support Operations (L1)",
        token="flowmind-lead-token-002",
    ),
    "flowmind-mgr-token-003": UserContext(
        user_id="USR-003",
        name="Elena Rostova",
        role=UserRole.TEAM_MANAGER,
        department="Customer Experience Management (L2)",
        token="flowmind-mgr-token-003",
    ),
    "flowmind-head-token-004": UserContext(
        user_id="USR-004",
        name="David Kim",
        role=UserRole.DEPARTMENT_HEAD,
        department="Customer Experience Leadership (L3)",
        token="flowmind-head-token-004",
    ),
    "flowmind-exec-token-005": UserContext(
        user_id="USR-005",
        name="Victoria Sterling",
        role=UserRole.EXECUTIVE,
        department="Executive Leadership (L4)",
        token="flowmind-exec-token-005",
    ),
    "flowmind-finance-token-006": UserContext(
        user_id="USR-006",
        name="Liam Patel",
        role=UserRole.FINANCE_REVIEWER,
        department="Finance Operations",
        token="flowmind-finance-token-006",
    ),
    "flowmind-vpfin-token-007": UserContext(
        user_id="USR-007",
        name="Sophia Zhao",
        role=UserRole.VP_FINANCE,
        department="Finance Leadership",
        token="flowmind-vpfin-token-007",
    ),
    "flowmind-admin-token-008": UserContext(
        user_id="USR-008",
        name="Alex Chen",
        role=UserRole.SYSTEM_ADMIN,
        department="IT & Systems Administration",
        token="flowmind-admin-token-008",
    ),
}
