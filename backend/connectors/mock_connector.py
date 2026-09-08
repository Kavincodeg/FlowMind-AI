"""
FlowMind AI - Mock Enterprise Connector (Phase 3)
Simulates action execution across enterprise systems (Zendesk, CRM routing, Payment Gateway).
ENFORCES CRITICAL CONSTRAINTS:
  1. No unauthorized execution: Action must have approval token or be marked auto-executed.
  2. Idempotency: Duplicate executions for the same workflow ID are detected and safely replayed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, Optional
import uuid

from backend.connectors.base import (
    EnterpriseConnector,
    ExecutionRequest,
    ExecutionResult,
    UnauthorizedExecutionError,
)
from backend.reasoning.models import ActionType

logger = logging.getLogger(__name__)


class MockEnterpriseConnector(EnterpriseConnector):
    """
    In-memory simulated connector for enterprise operational systems.
    Provides realistic delays, deterministic transaction IDs, and idempotency guarantees.
    """

    def __init__(self, simulate_latency_ms: float = 15.0, fail_on_purpose: bool = False):
        self.simulate_latency_ms = simulate_latency_ms
        self.fail_on_purpose = fail_on_purpose
        self._execution_history: Dict[str, ExecutionResult] = {}

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute an approved or auto-executable action with idempotency enforcement.
        """
        t0 = time.perf_counter()

        # 1. Non-negotiable security guard: verify authorization
        if not request.is_auto_executed and not request.approval_token:
            logger.error("Blocked execution attempt without approval token: workflow=%s", request.workflow_id)
            raise UnauthorizedExecutionError(
                f"Action '{request.action.action_type.value}' cannot execute without human approval verification."
            )

        # 2. Idempotency check: Return existing result if already executed
        if request.workflow_id in self._execution_history:
            existing = self._execution_history[request.workflow_id]
            logger.info("Idempotent replay for workflow %s: returning transaction %s", request.workflow_id, existing.transaction_id)
            return ExecutionResult(
                workflow_id=existing.workflow_id,
                transaction_id=existing.transaction_id,
                connector_name=existing.connector_name,
                action_type=existing.action_type,
                status=existing.status,
                details={**existing.details, "replay_timestamp": datetime.now(timezone.utc).isoformat()},
                executed_at=existing.executed_at,
                latency_ms=round((time.perf_counter() - t0) * 1000, 2),
                is_idempotent_replay=True,
            )

        # 3. Simulate operational system processing
        if self.simulate_latency_ms > 0:
            time.sleep(self.simulate_latency_ms / 1000.0)

        now_iso = datetime.now(timezone.utc).isoformat()
        short_id = request.workflow_id.replace("-", "")[:8].upper()

        # 4. Failure simulation mode (for testing resilience)
        if self.fail_on_purpose:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            failed_result = ExecutionResult(
                workflow_id=request.workflow_id,
                transaction_id=f"ERR-{short_id}",
                connector_name="MockEnterpriseConnector",
                action_type=request.action.action_type,
                status="FAILED",
                details={"error_message": "Simulated external enterprise connector timeout/failure."},
                executed_at=now_iso,
                latency_ms=round(elapsed_ms, 2),
                is_idempotent_replay=False,
            )
            self._execution_history[request.workflow_id] = failed_result
            return failed_result

        # 5. Route to simulated subsystems
        action_type = request.action.action_type
        details: Dict[str, Any] = {}

        if action_type == ActionType.ESCALATE_TICKET:
            tx_id = f"TKT-ESC-{short_id}"
            details = {
                "system": "Zendesk / Jira Service Management",
                "escalated_to_team": request.action.target_team,
                "escalation_tier": request.action.escalation_level.value if request.action.escalation_level else "L1",
                "urgency_assigned": request.action.urgency,
                "priority_queue": f"queue_{request.action.target_team.lower().replace(' ', '_')}",
                "simulated_ticket_number": f"INC-2026-{short_id}",
                "approver_audit": request.approver_id or "system_auto",
            }

        elif action_type == ActionType.TRANSFER_TEAM:
            tx_id = f"QUEUE-TRF-{short_id}"
            details = {
                "system": "Enterprise CRM Routing Engine",
                "reassigned_from": "Initial Routing",
                "reassigned_to": request.action.target_team,
                "transfer_rationale": request.action.parameters.get("routing_rationale", "Cross-team re-route"),
                "routing_batch_id": f"BATCH-{short_id}",
            }

        elif action_type == ActionType.ISSUE_REFUND_RECOMMENDATION:
            tx_id = f"RFND-BATCH-{short_id}"
            details = {
                "system": "Stripe / Core Banking Payment Gateway",
                "finance_queue": request.action.target_team,
                "batch_id": f"RFND-BATCH-{short_id}",
                "disbursement_state": "AUTHORIZED_PENDING_SETTLEMENT",
                "supervisor_signoff": request.approver_id or "manager_signoff",
            }

        elif action_type == ActionType.RESOLVE_STANDARD:
            tx_id = f"RES-STD-{short_id}"
            details = {
                "system": "Support Ticketing Resolution Engine",
                "resolution_code": "RESOLVED_STANDARD_SLA",
                "target_team": request.action.target_team,
                "closed_at": now_iso,
                "notification_dispatched": True,
            }

        else:
            tx_id = f"ACT-GEN-{short_id}"
            details = {
                "system": "Generic Operations Gateway",
                "action_type": action_type.value,
                "target_team": request.action.target_team,
            }

        elapsed_ms = (time.perf_counter() - t0) * 1000
        result = ExecutionResult(
            workflow_id=request.workflow_id,
            transaction_id=tx_id,
            connector_name="MockEnterpriseConnector",
            action_type=action_type,
            status="SUCCESS",
            details=details,
            executed_at=now_iso,
            latency_ms=round(elapsed_ms, 2),
            is_idempotent_replay=False,
        )

        # Store in idempotency history
        self._execution_history[request.workflow_id] = result
        return result
