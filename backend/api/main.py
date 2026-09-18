"""
FlowMind AI - FastAPI Application Entry Point (Phase 3)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as workflow_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: seed initial completed demo audit record on startup."""
    try:
        from backend.orchestrator.orchestrator import get_orchestrator
        from backend.orchestrator.models import ApprovalSubmission, ApprovalDecisionType, WorkflowStatus
        from backend.reasoning.models import ComplaintInvestigationRequest
        from backend.security.models import PRECONFIGURED_PERSONAS
        from backend.audit.service import get_audit_service

        audit_service = get_audit_service()
        if not audit_service.list_audits():
            orch = get_orchestrator()
            agent = PRECONFIGURED_PERSONAS["flowmind-agent-token-001"]
            mgr = PRECONFIGURED_PERSONAS["flowmind-mgr-token-003"]
            req = ComplaintInvestigationRequest(
                customer_id="CUST-1001",
                customer_name="Aarav Mehta",
                issue_summary="Overcharged on monthly subscription invoice INV-2024-001. Requesting refund of 25 dollars.",
            )
            inst = orch.start_investigation(req, requester=agent)
            if inst.status == WorkflowStatus.PENDING_APPROVAL:
                orch.submit_approval(
                    inst.workflow_id,
                    ApprovalSubmission(decision=ApprovalDecisionType.APPROVE, comments="Verified overcharge per Billing Policy Section 3.1."),
                    approver=mgr,
                )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to seed initial demo audit: %s", exc)
    yield


app = FastAPI(
    title="FlowMind AI - Enterprise Workflow Agent",
    description="Evidence-grounded, human-governed, auditable workflow AI agent for Customer Complaint Escalation.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow CORS for local React/TypeScript frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflow_router)


@app.get("/health", tags=["System"])
def health_check():
    """System health check endpoint."""
    return {"status": "ok", "service": "FlowMind AI", "version": "1.0.0"}


