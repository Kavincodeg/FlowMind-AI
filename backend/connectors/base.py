"""
FlowMind AI - Execution Connector Base & Contract (Phase 3)
Defines execution requests, results, and connector interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from backend.reasoning.models import ActionType, NextBestAction


class UnauthorizedExecutionError(RuntimeError):
    """Raised when an action execution is attempted without required human approval."""
    pass


class DuplicateExecutionError(RuntimeError):
    """Raised when an already executed action is submitted for duplicate execution."""
    pass


class ExecutionRequest(BaseModel):
    """Payload provided to an execution connector."""
    model_config = ConfigDict(extra="ignore")

    workflow_id: str
    action: NextBestAction
    approver_id: Optional[str] = None
    approver_role: Optional[str] = None
    is_auto_executed: bool = False
    approval_token: Optional[str] = None
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Result returned from enterprise execution connector."""
    model_config = ConfigDict(extra="ignore")

    workflow_id: str
    transaction_id: str
    connector_name: str
    action_type: ActionType
    status: str                       # "SUCCESS" | "FAILED"
    details: Dict[str, Any] = Field(default_factory=dict)
    executed_at: str
    latency_ms: float = 0.0
    is_idempotent_replay: bool = False


class EnterpriseConnector(ABC):
    """Abstract interface for enterprise action execution."""

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute the requested workflow action."""
        pass
