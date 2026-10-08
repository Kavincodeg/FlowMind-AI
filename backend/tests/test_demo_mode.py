"""
FlowMind AI - Task 2 Security Fix Tests

Tests that DEMO_MODE=false (default) properly blocks:
  1. GET /api/users/personas returns 404 (not the token list)
  2. Preset tokens are rejected (401) when DEMO_MODE is off
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.audit.service import AuditService, get_audit_service
from backend.connectors.mock_connector import MockEnterpriseConnector
from backend.orchestrator.orchestrator import WorkflowOrchestrator, get_orchestrator
from backend.reasoning.engine import ReasoningEngine
from backend.retrieval.mock_retriever import mock_retrieve


client = TestClient(app)

AGENT_TOKEN = "flowmind-agent-token-001"
ADMIN_TOKEN = "flowmind-admin-token-004"


@pytest.fixture(autouse=True)
def setup_test_orchestrator():
    """Configure the test orchestrator to use mock_retrieve for offline test execution."""
    test_audit_service = AuditService()
    test_orch = WorkflowOrchestrator(
        reasoning_engine=ReasoningEngine(retriever_fn=mock_retrieve),
        connector=MockEnterpriseConnector(simulate_latency_ms=0.0),
        audit_service=test_audit_service,
    )
    app.dependency_overrides[get_orchestrator] = lambda: test_orch
    app.dependency_overrides[get_audit_service] = lambda: test_audit_service
    yield test_orch
    app.dependency_overrides.clear()


class TestDemoModeOff:
    """When DEMO_MODE is false (or unset), security constraints must be enforced."""

    def test_personas_endpoint_returns_404_when_demo_mode_off(self):
        """
        GET /api/users/personas must return 404 when DEMO_MODE is not 'true'.
        The endpoint exposes tokens and must not be available in production.
        """
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            res = client.get("/api/users/personas")
        assert res.status_code == 404, (
            f"Expected 404 when DEMO_MODE=false, got {res.status_code}. "
            "This would expose auth tokens without login."
        )

    def test_personas_endpoint_returns_404_when_demo_mode_unset(self):
        """
        GET /api/users/personas must return 404 when DEMO_MODE env var is absent.
        """
        env = {k: v for k, v in os.environ.items() if k != "DEMO_MODE"}
        with patch.dict(os.environ, env, clear=True):
            res = client.get("/api/users/personas")
        assert res.status_code == 404, (
            f"Expected 404 when DEMO_MODE is unset, got {res.status_code}."
        )

    def test_preset_token_rejected_when_demo_mode_off(self):
        """
        Preset bearer tokens must be rejected with 401 when DEMO_MODE=false,
        even though they exist in PRECONFIGURED_PERSONAS.
        """
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            res = client.get(
                "/api/users/me",
                headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
            )
        assert res.status_code == 401, (
            f"Expected 401 when DEMO_MODE=false, got {res.status_code}. "
            "Hardcoded tokens must not authenticate in production mode."
        )

    def test_admin_token_rejected_when_demo_mode_off(self):
        """Admin token must also be rejected when DEMO_MODE=false."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            res = client.get(
                "/api/users/me",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        assert res.status_code == 401, (
            f"Expected 401 for admin token when DEMO_MODE=false, got {res.status_code}."
        )


class TestDemoModeOn:
    """When DEMO_MODE=true, the personas endpoint and preset tokens work normally."""

    def test_personas_endpoint_returns_200_when_demo_mode_on(self):
        """GET /api/users/personas returns the token list when DEMO_MODE=true."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            res = client.get("/api/users/personas")
        assert res.status_code == 200
        personas = res.json()
        assert len(personas) == 4
        roles = {p["role"] for p in personas}
        assert roles == {"support_agent", "team_lead", "manager", "admin"}

    def test_preset_token_accepted_when_demo_mode_on(self):
        """Preset bearer token authenticates when DEMO_MODE=true."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            res = client.get(
                "/api/users/me",
                headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "support_agent"
