"""
FlowMind AI - API Routes (Phase 3)
FastAPI REST endpoints for investigation, human approval, audit trails, and personas.
CRITICAL TRUST BOUNDARY: Approvals rely exclusively on server-resolved UserContext.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.audit.service import AuditService, get_audit_service
from backend.orchestrator.models import ApprovalSubmission, WorkflowInstance
from backend.orchestrator.orchestrator import WorkflowOrchestrator, get_orchestrator
from backend.reasoning.models import ComplaintInvestigationRequest
from backend.security.auth import get_current_user
from backend.security.models import PRECONFIGURED_PERSONAS, UserContext
from backend.security.rbac import RBACPermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Workflow & Governance"])


# ----------------------------------------------------------------------
# 1. User & Persona Endpoints
# ----------------------------------------------------------------------

@router.get("/users/personas", summary="List pre-configured test personas with tokens")
def list_personas() -> List[Dict[str, Any]]:
    """Retrieve pre-configured simulated personas for evaluation and UI testing."""
    return [
        {
            "user_id": p.user_id,
            "name": p.name,
            "role": p.role.value,
            "department": p.department,
            "token": p.token,
        }
        for p in PRECONFIGURED_PERSONAS.values()
    ]


@router.get("/users/me", summary="Get currently authenticated user identity")
def get_me(user: UserContext = Depends(get_current_user)) -> Dict[str, Any]:
    """Inspect the server-resolved identity of the current token."""
    return {
        "user_id": user.user_id,
        "name": user.name,
        "role": user.role.value,
        "department": user.department,
    }


# ----------------------------------------------------------------------
# 2. Workflow Endpoints
# ----------------------------------------------------------------------

@router.post("/workflow/investigate", summary="Start a customer complaint investigation")
def investigate_complaint(
    request: ComplaintInvestigationRequest,
    user: UserContext = Depends(get_current_user),
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """
    Initiates the investigation pipeline:
      retrieval -> reasoning -> recommendation -> (abstention | auto-execute | pending approval)
    """
    try:
        instance = orchestrator.start_investigation(request, requester=user)
        return _format_workflow_response(instance)
    except Exception as e:
        logger.exception("Investigation failed for customer %s", request.customer_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/{workflow_id}", summary="Get workflow state and details")
def get_workflow_details(
    workflow_id: str,
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """Retrieve the current state, evidence citations, and recommendation for a workflow."""
    instance = orchestrator.get_workflow(workflow_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return _format_workflow_response(instance)


@router.post("/workflow/{workflow_id}/decision", summary="Submit human approval decision (RBAC-gated)")
def submit_workflow_decision(
    workflow_id: str,
    submission: ApprovalSubmission,
    user: UserContext = Depends(get_current_user),
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """
    Submit a human governance decision (APPROVE, REJECT, or MODIFY).
    CRITICAL: Approver role is resolved strictly from the server session, preventing forgery.
    """
    try:
        instance = orchestrator.submit_approval(
            workflow_id=workflow_id,
            submission=submission,
            approver=user,
        )
        return _format_workflow_response(instance)

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

    except RBACPermissionDeniedError as rbac_err:
        logger.warning("RBAC denial on workflow %s: %s", workflow_id, rbac_err)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "RBAC_PERMISSION_DENIED",
                "message": rbac_err.reason,
                "user_role": rbac_err.user_role.value,
                "action_type": rbac_err.action_type.value,
            },
        )

    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))

    except Exception as e:
        logger.exception("Unexpected error processing approval on workflow %s", workflow_id)
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------------
# 3. Audit Endpoints
# ----------------------------------------------------------------------

@router.get("/workflow/{workflow_id}/audit", summary="Get complete tamper-evident audit trail")
def get_workflow_audit(
    workflow_id: str,
    audit_service: AuditService = Depends(get_audit_service),
) -> Dict[str, Any]:
    """Retrieve the finalized, state-dependent audit trail for a workflow."""
    try:
        return audit_service.export_audit_trail(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Audit record not found for workflow '{workflow_id}'.")


@router.get("/audits", summary="List all recorded audit records")
def list_all_audits(
    audit_service: AuditService = Depends(get_audit_service),
) -> List[Dict[str, Any]]:
    """List all completed audit logs in the system."""
    return [
        {
            "audit_id": a.audit_id,
            "workflow_id": a.workflow_id,
            "terminal_state": a.terminal_state,
            "is_complete": a.is_complete,
            "started_at": a.started_at,
            "completed_at": a.completed_at,
            "duration_ms": a.duration_ms,
        }
        for a in audit_service.list_audits()
    ]


# ----------------------------------------------------------------------
# Response Formatting Helper
# ----------------------------------------------------------------------

def _format_workflow_response(instance: WorkflowInstance) -> Dict[str, Any]:
    """Serialize WorkflowInstance into a clean client response."""
    ro = instance.reasoning_output
    return {
        "workflow_id": instance.workflow_id,
        "status": instance.status.value,
        "started_at": instance.started_at,
        "completed_at": instance.completed_at,
        "request": {
            "customer_id": instance.request.customer_id,
            "customer_name": instance.request.customer_name,
            "issue_summary": instance.request.issue_summary,
        },
        "reasoning": {
            "status": ro.status if ro else None,
            "abstention_reason": ro.abstention_reason.value if ro and ro.abstention_reason else None,
            "root_cause": ro.identified_root_cause if ro else None,
            "rationale": ro.rationale if ro else None,
            "confidence_score": ro.confidence_score if ro else None,
            "requires_human_approval": ro.requires_human_approval if ro else None,
            "indirect_injection_detected": ro.indirect_injection_detected if ro else None,
            "recommendation": ro.recommendation.model_dump() if ro and ro.recommendation else None,
            "citations": [c.model_dump() for c in ro.citations] if ro else [],
            "retrieval_summary": ro.retrieval_summary if ro else {},
        } if ro else None,
        "approval_record": instance.approval_record,
        "execution_record": instance.execution_record.model_dump() if instance.execution_record else None,
        "error_message": instance.error_message,
    }
