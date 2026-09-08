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
    MANAGER = "manager"
    ADMIN = "admin"


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
        return self.role == UserRole.ADMIN

    @property
    def is_manager_or_above(self) -> bool:
        return self.role in (UserRole.MANAGER, UserRole.ADMIN)

    @property
    def is_lead_or_above(self) -> bool:
        return self.role in (UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN)


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
        department="Support Operations",
        token="flowmind-lead-token-002",
    ),
    "flowmind-mgr-token-003": UserContext(
        user_id="USR-003",
        name="Elena Rostova",
        role=UserRole.MANAGER,
        department="Customer Experience Management",
        token="flowmind-mgr-token-003",
    ),
    "flowmind-admin-token-004": UserContext(
        user_id="USR-004",
        name="Alex Chen",
        role=UserRole.ADMIN,
        department="IT & Enterprise Operations",
        token="flowmind-admin-token-004",
    ),
}
