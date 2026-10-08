"""
FlowMind AI - API Response Models (Phase 3 / Task 3)

Pydantic schemas for all FastAPI endpoints.
Ensures the OpenAPI schema is complete and fully typed so openapi-typescript
can generate comprehensive TypeScript types for the frontend.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PersonaResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    name: str
    role: str
    department: str
    token: Optional[str] = None


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    name: str
    role: str
    department: str


class DemonstrationScenarioResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    category: str
    badge: str
    customer_id: str
    customer_name: str
    issue_summary: str
    expected_action: str
    required_role: str


class ComplaintRequestSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    customer_id: str
    customer_name: str
    issue_summary: str


class CitationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chunk_id: Optional[str] = None
    source_type: str = ""
    source_id: str = ""
    chunk_index: int = 0
    content: Optional[str] = None
    score: Optional[float] = None
    citation: Optional[str] = None
    snippet: Optional[str] = None
    relevance_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 0.0
    rationale: str = ""
    requires_human_approval: bool = False
    target_connector: Optional[str] = None
    target_team: Optional[str] = None
    escalation_level: Optional[str] = None
    urgency: Optional[str] = None


class ReasoningResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    status: Optional[str] = None
    abstention_reason: Optional[str] = None
    root_cause: Optional[str] = None
    identified_root_cause: Optional[str] = None
    customer_summary: Optional[str] = None
    rationale: Optional[str] = None
    confidence_score: Optional[float] = None
    requires_human_approval: Optional[bool] = None
    indirect_injection_detected: Optional[bool] = None
    recommendation: Optional[ActionRecommendationResponse] = None
    citations: List[CitationResponse] = Field(default_factory=list)
    retrieval_summary: Dict[str, Any] = Field(default_factory=dict)
    reasoning_time_ms: Optional[float] = None
    model_used: Optional[str] = None


class ExecutionRecordResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    workflow_id: str
    transaction_id: str
    connector_name: str
    action_type: str
    status: str
    details: Dict[str, Any] = Field(default_factory=dict)
    executed_at: str
    latency_ms: float = 0.0
    is_idempotent_replay: bool = False


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    workflow_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    request: ComplaintRequestSummary
    reasoning: Optional[ReasoningResponse] = None
    approval_record: Optional[Dict[str, Any]] = None
    execution_record: Optional[ExecutionRecordResponse] = None
    error_message: Optional[str] = None


class AuditTimeline(BaseModel):
    model_config = ConfigDict(extra="ignore")
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None


class AuditExportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    audit_id: str
    workflow_id: str
    terminal_state: str
    is_complete: bool
    timeline: AuditTimeline
    investigation: Dict[str, Any]
    human_governance: Optional[Dict[str, Any]] = None
    automation_execution: Optional[Dict[str, Any]] = None
    chain_events: List[Dict[str, Any]] = Field(default_factory=list)


class AuditVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    workflow_id: str
    chain_length: int
    valid: bool
    failed_at_index: Optional[int] = None
    failed_event_id: Optional[str] = None


class AuditSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    audit_id: str
    workflow_id: str
    terminal_state: str
    is_complete: bool
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None


class PolicyDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    filename: str
    title: str
    content: str
    size_bytes: int


class TicketListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tickets: List[Dict[str, Any]]
    total: int
    total_corpus: int
    categories: List[str]


class KnowledgeSearchChunk(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chunk_id: str
    source_type: str
    source_id: str
    chunk_index: int
    content: str
    similarity_score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    citation: str


class KnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query: str
    latency_ms: float
    total_retrieved: int
    chunks: List[KnowledgeSearchChunk]


class SecurityActionRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action_type: str
    label: str
    tier: str
    sensitive: bool
    description: str
    authorized_roles: List[str]
    requires_approval: bool


class GovernanceRulesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rejection_rationale_mandatory: bool = True
    parameter_modification_enforced: bool = True
    server_token_resolution: bool = True
    hash_chain_immutability: bool = True


class SecurityMatrixResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    roles: List[str]
    actions: List[SecurityActionRule]
    governance_rules: GovernanceRulesResponse = Field(default_factory=GovernanceRulesResponse)

