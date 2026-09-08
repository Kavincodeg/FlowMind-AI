"""
FlowMind AI - Workflow Orchestration Models (Phase 3)
Data models for workflow lifecycle states, approval submissions, and workflow instances.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.connectors.base import ExecutionResult
from backend.reasoning.models import ComplaintInvestigationRequest, NextBestAction, ReasoningOutput
from backend.security.models import UserContext


class WorkflowStatus(str, Enum):
    """Lifecycle states of an investigated complaint."""
    SUBMITTED = "SUBMITTED"
    INVESTIGATING = "INVESTIGATING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"
    AUTO_EXECUTED = "AUTO_EXECUTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABSTAINED = "ABSTAINED"


class ApprovalDecisionType(str, Enum):
    """Decision submitted by human governance authority."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


class ApprovalSubmission(BaseModel):
    """
    Client submission for human-in-the-loop governance.
    CRITICAL TRUST BOUNDARY: Approver identity and role are NEVER supplied here.
    They are strictly resolved server-side from the authenticated UserContext.
    """
    model_config = ConfigDict(extra="ignore")

    decision: ApprovalDecisionType
    rejection_reason: Optional[str] = None
    modified_action: Optional[NextBestAction] = None
    comments: Optional[str] = None


class WorkflowInstance(BaseModel):
    """Complete in-memory instance tracking a workflow lifecycle."""
    model_config = ConfigDict(extra="ignore")

    workflow_id: str
    status: WorkflowStatus
    started_at: str
    completed_at: Optional[str] = None
    request: ComplaintInvestigationRequest
    requester: UserContext
    reasoning_output: Optional[ReasoningOutput] = None
    approval_record: Optional[Dict[str, Any]] = None
    execution_record: Optional[ExecutionResult] = None
    error_message: Optional[str] = None
