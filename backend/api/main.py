"""
FlowMind AI - FastAPI Application Entry Point (Phase 3)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

# CORS: restrict to configured origins; default to localhost dev server only.
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflow_router)


class HealthResponse(BaseModel):
    status: str
    service: str = "FlowMind AI"
    version: str = "1.0.0"
    database: str  # "up" or "down"
    demo_mode: bool = False


def _is_demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "false").strip().lower() == "true"


def _check_database() -> dict:
    """
    Attempt a lightweight connection to the PostgreSQL / pgvector database.
    Returns {"status": "up"} or {"status": "down", "error": "<reason>"}.
    """
    try:
        from backend.retrieval.store import _get_dsn
        import psycopg2
        conn = psycopg2.connect(_get_dsn())
        conn.close()
        return {"status": "up"}
    except Exception as exc:
        return {"status": "down", "error": str(exc)}


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """
    System health check endpoint.

    Reports:
    - service status ("ok" or "degraded")
    - database connectivity ("up" or "down")
    - demo_mode status (bool)

    The frontend uses this to decide whether to show the
    "We can't reach the company knowledge base right now" banner
    and the demo accounts warning banner.
    """
    db_status = _check_database()
    overall_ok = db_status["status"] == "up"
    return HealthResponse(
        status="ok" if overall_ok else "degraded",
        service="FlowMind AI",
        version="1.0.0",
        database=db_status["status"],
        demo_mode=_is_demo_mode(),
    )

