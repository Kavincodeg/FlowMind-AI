"""
FlowMind AI - Reasoning Data Models (Phase 2)
Pydantic v2 data models for evidence-grounded recommendations, citations, and abstention.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionType(str, Enum):
    """Permitted action types in the Customer Complaint Escalation workflow."""
    ESCALATE_TICKET = "ESCALATE_TICKET"
    TRANSFER_TEAM = "TRANSFER_TEAM"
    REQUEST_CUSTOMER_INFO = "REQUEST_CUSTOMER_INFO"
    ISSUE_REFUND_RECOMMENDATION = "ISSUE_REFUND_RECOMMENDATION"
    RESOLVE_STANDARD = "RESOLVE_STANDARD"
    NO_ACTION = "NO_ACTION"


# High-impact actions that mandate human approval gate per project spec
SENSITIVE_ACTIONS = {
    ActionType.ESCALATE_TICKET,
    ActionType.ISSUE_REFUND_RECOMMENDATION,
    ActionType.TRANSFER_TEAM,
}


class EscalationLevel(str, Enum):
    """Escalation tier per company escalation policy."""
    L1 = "L1"   # Senior Support Agent (Within 4h)
    L2 = "L2"   # Team Manager (Within 2h)
    L3 = "L3"   # Department Head (Within 1h)
    L4 = "L4"   # Executive Team (Immediate)


class AbstentionReason(str, Enum):
    """Explicit justification when the agent refrains from recommending an action."""
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    NO_RELEVANT_POLICY = "NO_RELEVANT_POLICY"
    AMBIGUOUS_COMPLAINT = "AMBIGUOUS_COMPLAINT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CITATION_INTEGRITY_FAILURE = "CITATION_INTEGRITY_FAILURE"


class EvidenceCitation(BaseModel):
    """Explicit citation linking a factual assertion to a retrieved chunk."""
    model_config = ConfigDict(extra="ignore")

    source_type: str                  # "ticket" | "policy"
    source_id: str                    # e.g. "TKT-0033" or "escalation_policy.md"
    chunk_index: int = 0
    snippet: str = ""
    relevance_reason: str = ""
    policy_version: Optional[str] = None
    stored_citation: Optional[str] = None

    @model_validator(mode="after")
    def _compute_stored_citation(self) -> "EvidenceCitation":
        if self.source_type == "policy" and not self.stored_citation:
            from backend.retrieval.ingestion import POLICY_TITLE_MAP
            title = POLICY_TITLE_MAP.get(
                self.source_id,
                self.source_id.replace(".md", "").replace("_", " ").title()
            )
            ver_str = f" v{self.policy_version}" if self.policy_version else ""
            self.stored_citation = f"{title}{ver_str}"
        elif self.source_type == "ticket" and not self.stored_citation:
            self.stored_citation = f"Ticket {self.source_id}"
        return self

    @property
    def citation_label(self) -> str:
        if self.source_type == "ticket":
            return f"[Ticket {self.source_id}, chunk {self.chunk_index}]"
        ver_str = f" v{self.policy_version}" if self.policy_version else ""
        return f"[Policy: {self.source_id}{ver_str}, chunk {self.chunk_index}]"

    @property
    def citation(self) -> str:
        return self.stored_citation or self.citation_label


class NextBestAction(BaseModel):
    """Structured action proposal for the workflow."""
    model_config = ConfigDict(extra="ignore")

    action_type: ActionType
    target_team: str
    escalation_level: Optional[EscalationLevel] = None
    urgency: str = "medium"           # "low" | "medium" | "high" | "critical"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = True    # Sensitive actions must be gated behind approval


class ComplaintInvestigationRequest(BaseModel):
    """Input request to investigate a customer complaint."""
    model_config = ConfigDict(extra="ignore")

    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    issue_summary: str
    target_ticket_id: Optional[str] = None
    user_role: str = "support_agent"   # RBAC grounding: support_agent, team_lead, manager, admin
    top_k_tickets: int = Field(default=5, ge=1, le=20)
    top_k_policies: int = Field(default=4, ge=1, le=10)


class ReasoningOutput(BaseModel):
    """Complete output of the reasoning and recommendation layer."""
    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    status: str                       # "RECOMMENDATION_READY" | "ABSTAINED" | "ERROR"
    abstention_reason: Optional[AbstentionReason] = None
    customer_summary: str = ""
    identified_root_cause: str = ""
    recommendation: Optional[NextBestAction] = None
    rationale: str = ""
    citations: List[EvidenceCitation] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_human_approval: bool = True
    indirect_injection_detected: bool = False
    retrieval_summary: Dict[str, Any] = Field(default_factory=dict)
    reasoning_time_ms: float = 0.0
    model_used: str = "mock"

    @property
    def is_abstention(self) -> bool:
        return self.status == "ABSTAINED"

    @property
    def citation_labels(self) -> List[str]:
        return [c.citation_label for c in self.citations]
