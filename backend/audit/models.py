"""
FlowMind AI - Audit & Outcome Tracking Models (Phase 3)
Data models for complete, tamper-evident audit logging.
INVARIANT: Conditional audit completeness verified across all terminal states.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditRecord(BaseModel):
    """
    Comprehensive, auditable snapshot of an entire workflow lifecycle.
    """
    model_config = ConfigDict(extra="ignore")

    audit_id: str
    workflow_id: str
    terminal_state: str               # "COMPLETED" | "AUTO_EXECUTED" | "REJECTED" | "ABSTAINED" | "FAILED"
    started_at: str
    completed_at: str
    duration_ms: float = 0.0

    request_payload: Dict[str, Any] = Field(default_factory=dict)
    retrieval_summary: Dict[str, Any] = Field(default_factory=dict)
    evidence_citations: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_output: Dict[str, Any] = Field(default_factory=dict)
    approval_record: Optional[Dict[str, Any]] = None
    execution_record: Optional[Dict[str, Any]] = None

    @property
    def is_complete(self) -> bool:
        """
        State-dependent audit completeness verification (Fix 2).
        Validates that all required lifecycle stages for this specific terminal state are recorded.
        """
        # Baseline requirements across all completed workflows
        if not self.workflow_id or not self.started_at or not self.completed_at:
            return False
        if not self.request_payload:
            return False

        # 1. Human-Approved Execution (Happy Path)
        if self.terminal_state == "COMPLETED":
            return bool(
                self.reasoning_output
                and self.approval_record
                and self.approval_record.get("decision") in ("APPROVE", "MODIFY")
                and self.approval_record.get("approver_id")
                and self.execution_record
                and self.execution_record.get("status") == "SUCCESS"
            )

        # 2. Routine Non-Sensitive Action (Auto-Executed Path)
        elif self.terminal_state == "AUTO_EXECUTED":
            # Legitimately has no human approver
            return bool(
                self.reasoning_output
                and self.execution_record
                and self.execution_record.get("status") == "SUCCESS"
            )

        # 3. Human Rejected Recommendation
        elif self.terminal_state == "REJECTED":
            # Must record human rejection reason, legitimately has no execution record
            return bool(
                self.reasoning_output
                and self.approval_record
                and self.approval_record.get("decision") == "REJECT"
                and self.approval_record.get("rejection_reason")
                and self.execution_record is None
            )

        # 4. Agentic Abstention (Insufficient / Contradictory Evidence)
        elif self.terminal_state == "ABSTAINED":
            # Legitimately has no approval or execution
            return bool(
                self.reasoning_output
                and self.reasoning_output.get("status") == "ABSTAINED"
                and self.approval_record is None
                and self.execution_record is None
            )

        # 5. Failed State
        elif self.terminal_state == "FAILED":
            return bool(self.reasoning_output or self.execution_record)

        return False
