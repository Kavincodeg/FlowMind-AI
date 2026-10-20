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

import threading

from backend.audit.chain import build_event_chain
from backend.audit.models import AuditRecord
from backend.audit.service import AuditService, get_audit_service
from backend.connectors.base import (
    EnterpriseConnector,
    ExecutionRequest,
    ExecutionResult,
    UnauthorizedExecutionError,
    generate_approval_token,
    generate_auto_execution_token,
)
from backend.connectors.mock_connector import MockEnterpriseConnector
from backend.orchestrator.models import (
    ApprovalDecisionType,
    ApprovalSubmission,
    WorkflowInstance,
    WorkflowStatus,
)
from backend.reasoning.auto_execution import check_auto_execution, is_auto_executable
from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.models import ComplaintInvestigationRequest, NextBestAction
from backend.security.authority import compute_approval_due_at
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
        bypass_approval_gate: bool = False,
    ):
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.connector = connector or MockEnterpriseConnector()
        self.audit_service = audit_service or get_audit_service()
        self.bypass_approval_gate = bypass_approval_gate
        self._workflows: Dict[str, WorkflowInstance] = {}
        self._lock = threading.Lock()

    def start_investigation(
        self,
        request: ComplaintInvestigationRequest,
        requester: UserContext,
        precomputed_raw_response: Optional[str] = None,
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
            version=1,
            action_id=f"ACT-{workflow_id[:8].upper()}",
            started_by=requester.user_id,
            request=request,
            requester=requester,
        )
        self._workflows[workflow_id] = instance

        # 1. Transition to INVESTIGATING
        instance.status = WorkflowStatus.INVESTIGATING
        logger.info("Workflow %s: Investigating complaint for customer=%s", workflow_id, request.customer_id)

        # 2. Invoke Phase 2 Reasoning Engine
        reasoning_output = self.reasoning_engine.investigate(
            request, precomputed_raw_response=precomputed_raw_response
        )
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

        # 5. Handle Routine Action Auto-Execution (Customer Query Handling Policy 5 Conditions)
        auto_check = check_auto_execution(reasoning_output, request)
        instance.auto_execution_check = auto_check

        if is_auto_executable(reasoning_output, request) and reasoning_output.recommendation:
            logger.info("Workflow %s: Routine action qualifies for auto-execution.", workflow_id)
            instance.status = WorkflowStatus.AUTO_EXECUTED
            instance.status = WorkflowStatus.EXECUTING

            approval_token = generate_auto_execution_token(
                workflow_id, reasoning_output.recommendation.action_type.value
            )
            exec_req = ExecutionRequest(
                workflow_id=workflow_id,
                action=reasoning_output.recommendation,
                is_auto_executed=True,
                approval_token=approval_token,
                request_metadata={"customer_id": request.customer_id, "initiated_by": requester.user_id},
            )
            try:
                exec_res = self.connector.execute(exec_req)
            except Exception as exc:
                exec_res = ExecutionResult(
                    workflow_id=workflow_id,
                    transaction_id=f"ERR-{workflow_id[:8].upper()}",
                    connector_name="MockEnterpriseConnector",
                    action_type=reasoning_output.recommendation.action_type,
                    status="FAILED",
                    details={"error_message": f"Connector execution exception: {str(exc)}"},
                    executed_at=datetime.now(timezone.utc).isoformat(),
                    latency_ms=0.0,
                )
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

        # 6. Sensitive Action: Gated behind Human Approval (or bypassed in System D ablation)
        if self.bypass_approval_gate:
            assert isinstance(self.connector, MockEnterpriseConnector), (
                "CRITICAL SAFETY VIOLATION: WorkflowOrchestrator with bypass_approval_gate=True "
                f"MUST NEVER be bound to a live connector. Configured connector is '{type(self.connector).__name__}'."
            )
            if reasoning_output.recommendation:
                instance.status = WorkflowStatus.EXECUTING
                approval_token = generate_auto_execution_token(
                    workflow_id, reasoning_output.recommendation.action_type.value
                )
                exec_req = ExecutionRequest(
                    workflow_id=workflow_id,
                    action=reasoning_output.recommendation,
                    is_auto_executed=True,
                    approval_token=approval_token,
                    request_metadata={"customer_id": request.customer_id, "initiated_by": requester.user_id, "bypass_gate": True},
                )
                try:
                    exec_res = self.connector.execute(exec_req)
                except Exception as exc:
                    exec_res = ExecutionResult(
                        workflow_id=workflow_id,
                        transaction_id=f"ERR-{workflow_id[:8].upper()}",
                        connector_name="MockEnterpriseConnector",
                        action_type=reasoning_output.recommendation.action_type,
                        status="FAILED",
                        details={"error_message": f"Connector execution exception: {str(exc)}"},
                        executed_at=datetime.now(timezone.utc).isoformat(),
                        latency_ms=0.0,
                    )
                instance.execution_record = exec_res
                instance.status = WorkflowStatus.COMPLETED if exec_res.status == "SUCCESS" else WorkflowStatus.FAILED
                instance.completed_at = datetime.now(timezone.utc).isoformat()
                duration_ms = (time.perf_counter() - t0) * 1000
                self._finalize_audit(instance, terminal_state=instance.status.value, duration_ms=duration_ms)
                logger.info("Workflow %s: System D bypass executed: tx=%s", workflow_id, exec_res.transaction_id)
                return instance

        instance.status = WorkflowStatus.PENDING_APPROVAL
        if reasoning_output.recommendation:
            due_at = compute_approval_due_at(
                reasoning_output.recommendation,
                datetime.fromisoformat(started_at),
            )
            instance.approval_due_at = due_at.isoformat()
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
        Synchronized with self._lock to ensure concurrent submissions on the same action are strictly serialized.
        """
        with self._lock:
            instance = self.get_workflow(workflow_id)
            if not instance:
                raise KeyError(f"Workflow ID '{workflow_id}' not found.")

            if instance.status != WorkflowStatus.PENDING_APPROVAL:
                raise ValueError(
                    f"Cannot submit approval: Workflow '{workflow_id}' is in state '{instance.status.value}', not PENDING_APPROVAL."
                )

            if not instance.reasoning_output or not instance.reasoning_output.recommendation:
                raise ValueError(f"Workflow '{workflow_id}' contains no valid recommendation to approve.")

            # Validate action_id and version against forged or stale submissions
            if submission.action_id and instance.action_id and submission.action_id != instance.action_id:
                raise ValueError(f"Mismatched action ID: expected '{instance.action_id}', received '{submission.action_id}'.")
            if submission.version is not None and submission.version != instance.version:
                raise ValueError(f"Stale workflow version: expected version {instance.version}, received {submission.version}.")

            now_iso = datetime.now(timezone.utc).isoformat()
            started_dt = datetime.fromisoformat(instance.started_at)
            duration_ms = (datetime.now(timezone.utc) - started_dt).total_seconds() * 1000

            # --- REJECTION PATH ---
            if submission.decision == ApprovalDecisionType.REJECT:
                rej_reason = submission.rejection_reason or submission.comments or submission.note or submission.notes
                if not rej_reason or not rej_reason.strip():
                    raise ValueError("A rejection reason must be provided when rejecting a recommendation.")

                instance.status = WorkflowStatus.REJECTED
                instance.approval_record = {
                    "decision": "REJECT",
                    "approver_id": approver.user_id,
                    "approver_role": approver.role.value,
                    "rejection_reason": rej_reason.strip(),
                    "reason": rej_reason.strip(),
                    "comments": rej_reason.strip(),
                    "note": rej_reason.strip(),
                    "time": now_iso,
                    "timestamp": now_iso,
                }
                instance.completed_at = now_iso
                try:
                    self._finalize_audit(instance, terminal_state="REJECTED", duration_ms=duration_ms)
                except Exception as audit_exc:
                    instance.status = WorkflowStatus.PENDING_APPROVAL
                    instance.approval_record = None
                    instance.completed_at = None
                    raise RuntimeError(f"Atomic state transition failed: audit persistence error ({audit_exc}).") from audit_exc

                logger.info("Workflow %s: Rejected by %s (%s). Reason: %s", workflow_id, approver.name, approver.role.value, rej_reason)
                return instance

            # --- MODIFICATION PATH (Validate RBAC against MODIFIED action) ---
            elif submission.decision == ApprovalDecisionType.MODIFY:
                if not submission.modified_action:
                    raise ValueError("A modified_action must be provided when submitting a MODIFY decision.")

                mod_note = submission.note or submission.notes or submission.comments
                if not mod_note or not mod_note.strip():
                    raise ValueError("Modifying an action requires a written note.")

                target_action = submission.modified_action

                # RBAC must validate authority on the MODIFIED action
                verify_approval_permission(approver, target_action, workflow=instance)

                final_action_dict = {
                    "action_type": target_action.action_type.value if hasattr(target_action.action_type, "value") else str(target_action.action_type),
                    "level": target_action.escalation_level.value if target_action.escalation_level else None,
                    "team": target_action.target_team,
                    "amount": float(target_action.amount) if target_action.amount is not None else target_action.parameters.get("amount"),
                }

                instance.version += 1
                instance.status = WorkflowStatus.MODIFIED
                instance.approval_record = {
                    "decision": "MODIFY",
                    "approver_id": approver.user_id,
                    "approver_role": approver.role.value,
                    "final_action": final_action_dict,
                    "action_type": final_action_dict["action_type"],
                    "level": final_action_dict["level"],
                    "team": final_action_dict["team"],
                    "amount": final_action_dict["amount"],
                    "modified_action": target_action.model_dump(),
                    "note": mod_note.strip(),
                    "comments": mod_note.strip(),
                    "time": now_iso,
                    "timestamp": now_iso,
                }
                logger.info("Workflow %s: Modified and approved by %s (%s)", workflow_id, approver.name, approver.role.value)

            # --- APPROVE PATH ---
            elif submission.decision == ApprovalDecisionType.APPROVE:
                target_action = instance.reasoning_output.recommendation

                # Validate RBAC against proposed recommendation
                verify_approval_permission(approver, target_action, workflow=instance)

                final_action_dict = {
                    "action_type": target_action.action_type.value if hasattr(target_action.action_type, "value") else str(target_action.action_type),
                    "level": target_action.escalation_level.value if target_action.escalation_level else None,
                    "team": target_action.target_team,
                    "amount": float(target_action.amount) if target_action.amount is not None else target_action.parameters.get("amount"),
                }
                note_or_reason = submission.comments or submission.note or submission.notes or ""

                instance.status = WorkflowStatus.APPROVED
                instance.approval_record = {
                    "decision": "APPROVE",
                    "approver_id": approver.user_id,
                    "approver_role": approver.role.value,
                    "final_action": final_action_dict,
                    "action_type": final_action_dict["action_type"],
                    "level": final_action_dict["level"],
                    "team": final_action_dict["team"],
                    "amount": final_action_dict["amount"],
                    "note": note_or_reason,
                    "comments": note_or_reason,
                    "time": now_iso,
                    "timestamp": now_iso,
                }
                logger.info("Workflow %s: Approved as-is by %s (%s)", workflow_id, approver.name, approver.role.value)

            else:
                raise ValueError(f"Unknown approval decision: {submission.decision}")

            # --- EXECUTION PATH ---
            instance.status = WorkflowStatus.EXECUTING
            approval_token = generate_approval_token(workflow_id, approver.user_id, target_action.action_type.value)

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

            try:
                exec_res = self.connector.execute(exec_req)
            except Exception as exc:
                exec_res = ExecutionResult(
                    workflow_id=workflow_id,
                    transaction_id=f"ERR-{workflow_id[:8].upper()}",
                    connector_name="MockEnterpriseConnector",
                    action_type=target_action.action_type,
                    status="FAILED",
                    details={"error_message": f"Unexpected connector exception: {str(exc)}"},
                    executed_at=now_iso,
                    latency_ms=0.0,
                )
            instance.execution_record = exec_res

            # Atomic audit write enforcement: if audit persistence fails, roll back state change
            try:
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
            except Exception as audit_exc:
                instance.status = WorkflowStatus.PENDING_APPROVAL
                instance.execution_record = None
                instance.completed_at = None
                instance.approval_record = None
                logger.error("Workflow %s: Atomic audit rollback triggered: %s", workflow_id, audit_exc)
                raise RuntimeError(
                    f"Atomic state transition failed: audit persistence error ({audit_exc}). Action execution rolled back."
                ) from audit_exc

            return instance

    def retry_execution(
        self,
        workflow_id: str,
        approver: UserContext,
    ) -> WorkflowInstance:
        """
        Retry a workflow that previously ended in FAILED status due to a connector error.
        Verifies approver authority, re-dispatches to connector, and records the new state in the audit log.
        """
        with self._lock:
            instance = self.get_workflow(workflow_id)
            if not instance:
                raise KeyError(f"Workflow ID '{workflow_id}' not found.")

            if instance.status != WorkflowStatus.FAILED:
                raise ValueError(
                    f"Cannot retry execution: Workflow '{workflow_id}' is in state '{instance.status.value}', not FAILED."
                )

            target_action = None
            if instance.approval_record and instance.approval_record.get("modified_action"):
                target_action = NextBestAction.model_validate(instance.approval_record["modified_action"])
            elif instance.reasoning_output and instance.reasoning_output.recommendation:
                target_action = instance.reasoning_output.recommendation

            if not target_action:
                raise ValueError(f"Workflow '{workflow_id}' contains no executable action proposal to retry.")

            verify_approval_permission(approver, target_action, workflow=instance)

            started_dt = datetime.fromisoformat(instance.started_at)
            now_iso = datetime.now(timezone.utc).isoformat()
            instance.status = WorkflowStatus.EXECUTING

            approval_token = generate_approval_token(workflow_id, approver.user_id, target_action.action_type.value)
            exec_req = ExecutionRequest(
                workflow_id=workflow_id,
                action=target_action,
                approver_id=approver.user_id,
                approver_role=approver.role.value,
                approval_token=approval_token,
                request_metadata={
                    "customer_id": instance.request.customer_id,
                    "retry": True,
                },
            )

            try:
                exec_res = self.connector.execute(exec_req)
            except Exception as exc:
                exec_res = ExecutionResult(
                    workflow_id=workflow_id,
                    transaction_id=f"ERR-{workflow_id[:8].upper()}",
                    connector_name="MockEnterpriseConnector",
                    action_type=target_action.action_type,
                    status="FAILED",
                    details={"error_message": f"Retry connector exception: {str(exc)}"},
                    executed_at=now_iso,
                    latency_ms=0.0,
                )

            instance.execution_record = exec_res

            if exec_res.status == "SUCCESS":
                instance.status = WorkflowStatus.COMPLETED
                instance.completed_at = datetime.now(timezone.utc).isoformat()
                instance.error_message = None
                duration_ms = (datetime.now(timezone.utc) - started_dt).total_seconds() * 1000
                self._finalize_audit(instance, terminal_state="COMPLETED", duration_ms=duration_ms, is_retry=True)
                logger.info("Workflow %s: Successfully executed on retry: tx=%s", workflow_id, exec_res.transaction_id)
            else:
                instance.status = WorkflowStatus.FAILED
                instance.error_message = f"Retry failed: {exec_res.details}"
                instance.completed_at = datetime.now(timezone.utc).isoformat()
                duration_ms = (datetime.now(timezone.utc) - started_dt).total_seconds() * 1000
                self._finalize_audit(instance, terminal_state="FAILED", duration_ms=duration_ms, is_retry=True)

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

    def _finalize_audit(self, instance: WorkflowInstance, terminal_state: str, duration_ms: float, is_retry: bool = False) -> None:
        """Create and store a finalized AuditRecord with a real SHA-256 hash chain.

        The chain_events field is built by build_event_chain() from audit/chain.py,
        which computes a genuine SHA-256 per-event hash linking each lifecycle stage
        to the previous one.  Once recorded, this chain is never recomputed or
        overwritten (enforced by AuditService.record_audit()).
        """
        ro = instance.reasoning_output
        wf_id = instance.workflow_id
        started_at = instance.started_at
        completed_at = instance.completed_at or datetime.now(timezone.utc).isoformat()

        # ------------------------------------------------------------------
        # Build content payloads for each lifecycle event.
        # All Pydantic models are serialised via .model_dump(mode='json') so that
        # datetimes, UUIDs and Enums become JSON-native types before canonical_json()
        # is called.  The verify path applies the same pre-conversion, ensuring
        # write-time and verify-time hashes are byte-for-bit identical.
        # ------------------------------------------------------------------
        request_payload = {
            "customer_id": instance.request.customer_id,
            "customer_name": instance.request.customer_name,
            "issue_summary": instance.request.issue_summary,
            "requester_id": instance.requester.user_id,
            "requester_role": instance.requester.role.value,
        }
        retrieval_summary = ro.retrieval_summary if ro else {}
        evidence_citations = [c.model_dump(mode="json") for c in ro.citations] if ro else []
        reasoning_output_dict = {
            "status": ro.status,
            "abstention_reason": ro.abstention_reason.value if ro and ro.abstention_reason else None,
            "root_cause": ro.identified_root_cause,
            "rationale": ro.rationale,
            "confidence_score": ro.confidence_score,
            "indirect_injection_detected": ro.indirect_injection_detected,
            "recommendation": ro.recommendation.model_dump(mode="json") if ro and ro.recommendation else None,
        } if ro else {}

        approval_record = instance.approval_record  # already a plain dict
        execution_record = instance.execution_record.model_dump(mode="json") if instance.execution_record else None

        # ------------------------------------------------------------------
        # Assemble raw lifecycle events (no hashes yet)
        # ------------------------------------------------------------------
        short_id = wf_id[:8]
        raw_events = [
            {
                "event_id": f"EVT-001-{short_id}",
                "stage": "REQUEST_RECEIVED",
                "timestamp": started_at,
                "actor": instance.requester.user_id,
                "details": request_payload,
            },
            {
                "event_id": f"EVT-002-{short_id}",
                "stage": "EVIDENCE_RETRIEVED",
                "timestamp": started_at,
                "actor": "VectorRetriever (pgvector)",
                "details": {
                    "retrieval_summary": retrieval_summary,
                    "evidence_citations": evidence_citations,
                },
            },
            {
                "event_id": f"EVT-003-{short_id}",
                "stage": "REASONING_COMPLETED",
                "timestamp": started_at,
                "actor": "ReasoningEngine",
                "details": reasoning_output_dict,
            },
        ]

        if instance.auto_execution_check is not None:
            raw_events.append({
                "event_id": f"EVT-003B-{short_id}",
                "stage": "AUTO_EXECUTION_EVALUATED",
                "timestamp": started_at,
                "actor": "AutoExecutionPolicyEngine",
                "details": instance.auto_execution_check,
            })

        if approval_record is not None:
            raw_events.append({
                "event_id": f"EVT-004-{short_id}",
                "stage": "APPROVAL_SUBMITTED",
                "timestamp": approval_record.get("timestamp", completed_at),
                "actor": approval_record.get("approver_id", "unknown"),
                "details": approval_record,
            })

        if execution_record is not None:
            raw_events.append({
                "event_id": f"EVT-005-{short_id}",
                "stage": "ACTION_DISPATCHED",
                "timestamp": execution_record.get("timestamp", completed_at),
                "actor": execution_record.get("dispatched_to", "MockEnterpriseConnector"),
                "details": execution_record,
            })

        # ------------------------------------------------------------------
        # Compute the real SHA-256 hash chain
        # ------------------------------------------------------------------
        chain_events = build_event_chain(raw_events)

        # ------------------------------------------------------------------
        # Persist the AuditRecord
        # ------------------------------------------------------------------
        audit_record = AuditRecord(
            audit_id=str(uuid.uuid4()),
            workflow_id=wf_id,
            terminal_state=terminal_state,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
            request_payload=request_payload,
            retrieval_summary=retrieval_summary,
            evidence_citations=evidence_citations,
            reasoning_output=reasoning_output_dict,
            auto_execution_check=instance.auto_execution_check,
            approval_record=approval_record,
            execution_record=execution_record,
            chain_events=chain_events,
        )
        self.audit_service.record_audit(audit_record, is_retry=is_retry)


# Global singleton orchestrator
_orchestrator: Optional[WorkflowOrchestrator] = None


def get_orchestrator() -> WorkflowOrchestrator:
    """Dependency / accessor for the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator