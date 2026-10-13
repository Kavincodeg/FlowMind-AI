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
    """Lifespan context manager: seed initial completed demo audit records and workflows on startup."""
    try:
        from datetime import datetime, timezone
        from decimal import Decimal
        from backend.orchestrator.orchestrator import get_orchestrator
        from backend.orchestrator.models import WorkflowInstance, ExecutionResult, WorkflowStatus
        from backend.reasoning.models import (
            ComplaintInvestigationRequest,
            ReasoningOutput,
            NextBestAction,
            ActionType,
            EvidenceCitation,
        )
        from backend.security.models import PRECONFIGURED_PERSONAS
        from backend.audit.service import get_audit_service

        orch = get_orchestrator()
        audit_service = get_audit_service()
        if not audit_service.list_audits():
            now_iso = datetime.now(timezone.utc).isoformat()
            agent = PRECONFIGURED_PERSONAS["flowmind-agent-token-001"]
            lead = PRECONFIGURED_PERSONAS["flowmind-lead-token-002"]

            # 1. WF-CASE-101: Pending approval $300 refund (For Team Lead boundary verification)
            wf_300 = WorkflowInstance(
                workflow_id="WF-CASE-101",
                status=WorkflowStatus.PENDING_APPROVAL,
                started_at=now_iso,
                started_by=agent.user_id,
                requester=agent,
                request=ComplaintInvestigationRequest(
                    customer_id="CUST-3001",
                    customer_name="Alice Smith",
                    issue_summary="Requesting $300 billing refund for service outage during SLA window.",
                    priority="medium",
                    category="billing",
                ),
                reasoning_output=ReasoningOutput(
                    status="RECOMMENDATION_READY",
                    customer_summary="Customer Alice Smith experienced downtime and requested a $300 refund.",
                    identified_root_cause="Service outage during scheduled uptime.",
                    recommendation=NextBestAction(
                        action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
                        amount=Decimal("300.00"),
                        parameters={"amount": 300.0, "reason": "Downtime credit"},
                    ),
                    rationale="Customer eligible for $300 billing credit under Section 3.2.",
                    citations=[EvidenceCitation(source_type="policy", source_id="refund_policy.md")],
                    confidence_score=0.92,
                    requires_human_approval=True,
                ),
            )
            orch._workflows[wf_300.workflow_id] = wf_300

            # 2. WF-CASE-102: Pending approval $600 refund (For Department Head boundary verification)
            wf_600 = WorkflowInstance(
                workflow_id="WF-CASE-102",
                status=WorkflowStatus.PENDING_APPROVAL,
                started_at=now_iso,
                started_by=lead.user_id,
                requester=lead,
                request=ComplaintInvestigationRequest(
                    customer_id="CUST-6001",
                    customer_name="Bob Jones",
                    issue_summary="Enterprise account requesting $600 refund for billing error.",
                    priority="high",
                    category="billing",
                ),
                reasoning_output=ReasoningOutput(
                    status="RECOMMENDATION_READY",
                    customer_summary="Customer Bob Jones requests $600 enterprise adjustment.",
                    identified_root_cause="Enterprise billing discrepancy.",
                    recommendation=NextBestAction(
                        action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
                        amount=Decimal("600.00"),
                        parameters={"amount": 600.0, "reason": "Enterprise adjustment"},
                    ),
                    rationale="Enterprise refund above $500 requires Finance review per matrix.",
                    citations=[EvidenceCitation(source_type="policy", source_id="approval_authority_matrix.md")],
                    confidence_score=0.95,
                    requires_human_approval=True,
                ),
            )
            orch._workflows[wf_600.workflow_id] = wf_600

            # 3. WF-CASE-103: Auto-executed case (Routine password reset with all 5 conditions met)
            wf_auto = WorkflowInstance(
                workflow_id="WF-CASE-103",
                status=WorkflowStatus.AUTO_EXECUTED,
                started_at=now_iso,
                completed_at=now_iso,
                started_by=agent.user_id,
                requester=agent,
                request=ComplaintInvestigationRequest(
                    customer_id="CUST-AUTO",
                    customer_name="Sam Taylor",
                    issue_summary="Customer requests guidance on how to update profile password.",
                    priority="low",
                    category="general",
                    flags=[],
                ),
                reasoning_output=ReasoningOutput(
                    status="RECOMMENDATION_READY",
                    customer_summary="Customer Sam Taylor asked for standard password assistance.",
                    identified_root_cause="General self-service inquiry.",
                    recommendation=NextBestAction(
                        action_type=ActionType.RESOLVE_STANDARD,
                        amount=None,
                        parameters={},
                    ),
                    rationale="Standard self-service password reset guidance provided per KB guidelines.",
                    citations=[
                        EvidenceCitation(source_type="policy", source_id="customer_query_handling_policy.md"),
                        EvidenceCitation(source_type="policy", source_id="kb_guidelines.md"),
                    ],
                    confidence_score=0.98,
                    requires_human_approval=False,
                ),
                auto_execution_check={
                    "passed": True,
                    "no_monetary_liability": True,
                    "low_standard_priority": True,
                    "no_sensitive_flags": True,
                    "routine_category": True,
                    "two_policy_citations": True,
                    "conditions_met": [
                        "no_monetary_liability",
                        "low_standard_priority",
                        "no_sensitive_flags",
                        "routine_category",
                        "two_policy_citations",
                    ],
                },
                execution_record=ExecutionResult(
                    workflow_id="WF-CASE-103",
                    action_type=ActionType.RESOLVE_STANDARD,
                    status="SUCCESS",
                    connector_name="EmailSupportConnector",
                    transaction_id="TX-AUTO-2024-001",
                    details={"message": "Sent password reset guide email to customer."},
                    executed_at=now_iso,
                    latency_ms=120.0,
                ),
            )
            orch._workflows[wf_auto.workflow_id] = wf_auto
            orch._finalize_audit(wf_auto, terminal_state="AUTO_EXECUTED", duration_ms=150.0)
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

