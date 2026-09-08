"""
FlowMind AI - Workflow Orchestrator (Phase 3)
Coordinates the complete lifecycle of customer complaint investigations:
  retrieve -> reason -> recommend -> approve (RBAC-gated) -> execute (mock connector) -> audit
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Dict, Optional
import uuid

from backend.audit.models import AuditRecord
from backend.audit.service import AuditService, get_audit_service
from backend.connectors.base import EnterpriseConnector, ExecutionRequest, UnauthorizedExecutionError
from backend.connectors.mock_connector import MockEnterpriseConnector
from backend.orchestrator.models import (
    ApprovalDecisionType,
    ApprovalSubmission,
    WorkflowInstance,
    WorkflowStatus,
)
from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.models import ComplaintInvestigationRequest
from backend.security.models import UserContext
from backend.security.rbac import verify_approval_permission

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Finite State Machine and orchestration engine for complaint investigations.
    """

    def __init__(
        self,
        reasoning_engine: Optional[ReasoningEngine] = None,
        connector: Optional[EnterpriseConnector] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.connector = connector or MockEnterpriseConnector()
        self.audit_service = audit_service or get_audit_service()
        self._workflows: Dict[str, WorkflowInstance] = {}

    def start_investigation(
        self,
        request: ComplaintInvestigationRequest,
        requester: UserContext,
    ) -> WorkflowInstance:
        """
        Initiate a complaint investigation workflow.
        Transitions: SUBMITTED -> INVESTIGATING -> (ABSTAINED | PENDING_APPROVAL | AUTO_EXECUTED -> COMPLETED)
        """
        workflow_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()

        instance = WorkflowInstance(
            workflow_id=workflow_id,
            status=WorkflowStatus.SUBMITTED,
            started_at=started_at,
            request=request,
            requester=requester,
        )
        self._workflows[workflow_id] = instance

        # 1. Transition to INVESTIGATING
        instance.status = WorkflowStatus.INVESTIGATING
        logger.info("Workflow %s: Investigating complaint for customer=%s", workflow_id, request.customer_id)

        # 2. Invoke Phase 2 Reasoning Engine
        reasoning_output = self.reasoning_engine.investigate(request)
        instance.reasoning_output = reasoning_output

        # 3. Handle Terminal Abstention
        if reasoning_output.is_abstention or reasoning_output.status == "ABSTAINED":
            instance.status = WorkflowStatus.ABSTAINED
            instance.completed_at = datetime.now(timezone.utc).isoformat()
            duration_ms = (time.perf_counter() - t0) * 1000
            self._finalize_audit(instance, terminal_state="ABSTAINED", duration_ms=duration_ms)
            logger.info("Workflow %s: Abstained (%s)", workflow_id, reasoning_output.abstention_reason)
            return instance

        # 4. Handle Terminal Error in Reasoning
        if reasoning_output.status == "ERROR":
            instance.status = WorkflowStatus.FAILED
            instance.error_message = reasoning_output.identified_root_cause
            instance.completed_at = datetime.now(timezone.utc).isoformat()
            duration_ms = (time.perf_counter() - t0) * 1000
            self._finalize_audit(instance, terminal_state="FAILED", duration_ms=duration_ms)
            logger.error("Workflow %s: Reasoning failed (%s)", workflow_id, instance.error_message)
            return instance

        # 5. Handle Routine Action Auto-Execution (Fix 3)
        # If requires_human_approval is False (routine action in clean non-injected context)
        if not reasoning_output.requires_human_approval and reasoning_output.recommendation:
            logger.info("Workflow %s: Routine action qualifies for auto-execution.", workflow_id)
            instance.status = WorkflowStatus.AUTO_EXECUTED
            instance.status = WorkflowStatus.EXECUTING

            exec_req = ExecutionRequest(
                workflow_id=workflow_id,
                action=reasoning_output.recommendation,
                is_auto_executed=True,
                request_metadata={"customer_id": request.customer_id, "initiated_by": requester.user_id},
            )
            exec_res = self.connector.execute(exec_req)
            instance.execution_record = exec_res

            if exec_res.status == "SUCCESS":
                instance.status = WorkflowStatus.COMPLETED
                instance.completed_at = datetime.now(timezone.utc).isoformat()
                duration_ms = (time.perf_counter() - t0) * 1000
                self._finalize_audit(instance, terminal_state="AUTO_EXECUTED", duration_ms=duration_ms)
                logger.info("Workflow %s: Auto-execution completed successfully: tx=%s", workflow_id, exec_res.transaction_id)
            else:
                instance.status = WorkflowStatus.FAILED
                instance.error_message = f"Connector execution failure: {exec_res.details}"
                instance.completed_at = datetime.now(timezone.utc).isoformat()
                duration_ms = (time.perf_counter() - t0) * 1000
                self._finalize_audit(instance, terminal_state="FAILED", duration_ms=duration_ms)

            return instance

        # 6. Sensitive Action: Gated behind Human Approval
        instance.status = WorkflowStatus.PENDING_APPROVAL
        logger.info(
            "Workflow %s: Paused for human approval. Action=%s, Tier=%s",
            workflow_id,
            reasoning_output.recommendation.action_type.value if reasoning_output.recommendation else "N/A",
            reasoning_output.recommendation.escalation_level.value if reasoning_output.recommendation and reasoning_output.recommendation.escalation_level else "N/A",
        )
        return instance

    def submit_approval(
        self,
        workflow_id: str,
        submission: ApprovalSubmission,
        approver: UserContext,
    ) -> WorkflowInstance:
        """
        Process human-in-the-loop governance decision with server-resolved UserContext.
        Transitions: PENDING_APPROVAL -> (APPROVED | MODIFIED | REJECTED) -> EXECUTING -> COMPLETED
        """
        instance = self.get_workflow(workflow_id)
        if not instance:
            raise KeyError(f"Workflow ID '{workflow_id}' not found.")

        if instance.status != WorkflowStatus.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot submit approval: Workflow '{workflow_id}' is in state '{instance.status.value}', not PENDING_APPROVAL."
            )

        if not instance.reasoning_output or not instance.reasoning_output.recommendation:
            raise ValueError(f"Workflow '{workflow_id}' contains no valid recommendation to approve.")

        now_iso = datetime.now(timezone.utc).isoformat()
        started_dt = datetime.fromisoformat(instance.started_at)
        duration_ms = (datetime.now(timezone.utc) - started_dt).total_seconds() * 1000

        # --- REJECTION PATH ---
        if submission.decision == ApprovalDecisionType.REJECT:
            if not submission.rejection_reason or not submission.rejection_reason.strip():
                raise ValueError("A rejection reason must be provided when rejecting a recommendation.")

            instance.status = WorkflowStatus.REJECTED
            instance.approval_record = {
                "decision": "REJECT",
                "approver_id": approver.user_id,
                "approver_role": approver.role.value,
                "rejection_reason": submission.rejection_reason.strip(),
                "comments": submission.comments or "",
                "timestamp": now_iso,
            }
            instance.completed_at = now_iso
            self._finalize_audit(instance, terminal_state="REJECTED", duration_ms=duration_ms)
            logger.info("Workflow %s: Rejected by %s (%s). Reason: %s", workflow_id, approver.name, approver.role.value, submission.rejection_reason)
            return instance

        # --- MODIFICATION PATH (Fix 1: Validate RBAC against MODIFIED action) ---
        elif submission.decision == ApprovalDecisionType.MODIFY:
            if not submission.modified_action:
                raise ValueError("A modified_action must be provided when submitting a MODIFY decision.")

            target_action = submission.modified_action

            # FIX 1: RBAC must validate the user's authority on the MODIFIED action
            verify_approval_permission(approver, target_action)

            instance.status = WorkflowStatus.MODIFIED
            instance.approval_record = {
                "decision": "MODIFY",
                "approver_id": approver.user_id,
                "approver_role": approver.role.value,
                "modified_action": target_action.model_dump(),
                "comments": submission.comments or "",
                "timestamp": now_iso,
            }
            logger.info("Workflow %s: Modified and approved by %s (%s)", workflow_id, approver.name, approver.role.value)

        # --- APPROVE PATH ---
        elif submission.decision == ApprovalDecisionType.APPROVE:
            target_action = instance.reasoning_output.recommendation

            # Validate RBAC against proposed recommendation
            verify_approval_permission(approver, target_action)

            instance.status = WorkflowStatus.APPROVED
            instance.approval_record = {
                "decision": "APPROVE",
                "approver_id": approver.user_id,
                "approver_role": approver.role.value,
                "comments": submission.comments or "",
                "timestamp": now_iso,
            }
            logger.info("Workflow %s: Approved as-is by %s (%s)", workflow_id, approver.name, approver.role.value)

        else:
            raise ValueError(f"Unknown approval decision: {submission.decision}")

        # --- EXECUTION PATH ---
        instance.status = WorkflowStatus.EXECUTING
        approval_token = f"APP-VERIFIED-{workflow_id}-{approver.user_id}"

        exec_req = ExecutionRequest(
            workflow_id=workflow_id,
            action=target_action,
            approver_id=approver.user_id,
            approver_role=approver.role.value,
            approval_token=approval_token,
            request_metadata={
                "customer_id": instance.request.customer_id,
                "decision_type": submission.decision.value,
            },
        )

        exec_res = self.connector.execute(exec_req)
        instance.execution_record = exec_res

        if exec_res.status == "SUCCESS":
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = datetime.now(timezone.utc).isoformat()
            duration_ms = (datetime.now(timezone.utc) - started_dt).total_seconds() * 1000
            self._finalize_audit(instance, terminal_state="COMPLETED", duration_ms=duration_ms)
            logger.info("Workflow %s: Successfully executed via connector: tx=%s", workflow_id, exec_res.transaction_id)
        else:
            instance.status = WorkflowStatus.FAILED
            instance.error_message = f"Execution failed: {exec_res.details}"
            instance.completed_at = datetime.now(timezone.utc).isoformat()
            duration_ms = (datetime.now(timezone.utc) - started_dt).total_seconds() * 1000
            self._finalize_audit(instance, terminal_state="FAILED", duration_ms=duration_ms)

        return instance

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowInstance]:
        """Retrieve a workflow instance by ID."""
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> Dict[str, WorkflowInstance]:
        """Retrieve all active/completed workflow instances."""
        return dict(self._workflows)

    # ------------------------------------------------------------------
    # Internal Audit Helper
    # ------------------------------------------------------------------

    def _finalize_audit(self, instance: WorkflowInstance, terminal_state: str, duration_ms: float) -> None:
        """Create and store a finalized AuditRecord."""
        ro = instance.reasoning_output
        audit_record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            workflow_id=instance.workflow_id,
            terminal_state=terminal_state,
            started_at=instance.started_at,
            completed_at=instance.completed_at or datetime.now(timezone.utc).isoformat(),
            duration_ms=round(duration_ms, 2),
            request_payload={
                "customer_id": instance.request.customer_id,
                "customer_name": instance.request.customer_name,
                "issue_summary": instance.request.issue_summary,
                "requester_id": instance.requester.user_id,
                "requester_role": instance.requester.role.value,
            },
            retrieval_summary=ro.retrieval_summary if ro else {},
            evidence_citations=[c.model_dump() for c in ro.citations] if ro else [],
            reasoning_output={
                "status": ro.status,
                "abstention_reason": ro.abstention_reason.value if ro and ro.abstention_reason else None,
                "root_cause": ro.identified_root_cause,
                "rationale": ro.rationale,
                "confidence_score": ro.confidence_score,
                "indirect_injection_detected": ro.indirect_injection_detected,
                "recommendation": ro.recommendation.model_dump() if ro and ro.recommendation else None,
            } if ro else {},
            approval_record=instance.approval_record,
            execution_record=instance.execution_record.model_dump() if instance.execution_record else None,
        )
        self.audit_service.record_audit(audit_record)


# Global singleton orchestrator
_orchestrator: Optional[WorkflowOrchestrator] = None


def get_orchestrator() -> WorkflowOrchestrator:
    """Dependency / accessor for the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator
