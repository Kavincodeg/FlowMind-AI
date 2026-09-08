"""
FlowMind AI - FastAPI Application Entry Point (Phase 3)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as workflow_router

app = FastAPI(
    title="FlowMind AI - Enterprise Workflow Agent",
    description="Evidence-grounded, human-governed, auditable workflow AI agent for Customer Complaint Escalation.",
    version="1.0.0",
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
