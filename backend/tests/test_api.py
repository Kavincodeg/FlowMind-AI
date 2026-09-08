"""
FlowMind AI - End-to-End API Tests (Phase 3)
Verifies:
  1. Persona and authentication endpoints.
  2. Investigation and approval lifecycle via REST API.
  3. CRITICAL TEST: Request body role forgery is rejected in favor of server-resolved identity.
  4. Audit trail inspection via REST API.
"""
from fastapi.testclient import TestClient
import pytest

from backend.api.main import app

client = TestClient(app)

AGENT_TOKEN = "flowmind-agent-token-001"
LEAD_TOKEN = "flowmind-lead-token-002"
MGR_TOKEN = "flowmind-mgr-token-003"
ADMIN_TOKEN = "flowmind-admin-token-004"


class TestAuthAndPersonaEndpoints:

    def test_list_personas(self):
        res = client.get("/api/users/personas")
        assert res.status_code == 200
        personas = res.json()
        assert len(personas) == 4
        roles = {p["role"] for p in personas}
        assert roles == {"support_agent", "team_lead", "manager", "admin"}

    def test_get_me_requires_authentication(self):
        # No token -> 401 Unauthorized
        res = client.get("/api/users/me")
        assert res.status_code == 401

        # Valid bearer token -> 200
        res = client.get("/api/users/me", headers={"Authorization": f"Bearer {MGR_TOKEN}"})
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Elena Rostova"
        assert data["role"] == "manager"


class TestWorkflowAPIEndToEnd:

    def test_investigate_and_approve_flow(self):
        # 1. Support agent starts investigation on repeat complaint
        payload = {
            "customer_id": "CUST-1002",
            "customer_name": "Arjun Sharma",
            "issue_summary": "Damaged goods reported for fourth time. Escalation required.",
        }
        res = client.post(
            "/api/workflow/investigate",
            json=payload,
            headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
        )
        assert res.status_code == 200
        data = res.json()
        wf_id = data["workflow_id"]
        assert data["status"] == "PENDING_APPROVAL"
        assert data["reasoning"]["recommendation"]["action_type"] == "ESCALATE_TICKET"
        assert data["reasoning"]["recommendation"]["escalation_level"] == "L2"

        # 2. Get workflow details
        res_get = client.get(f"/api/workflow/{wf_id}")
        assert res_get.status_code == 200
        assert res_get.json()["workflow_id"] == wf_id

        # 3. Manager approves
        approval_payload = {
            "decision": "APPROVE",
            "comments": "Approved via REST API by CX Manager.",
        }
        res_app = client.post(
            f"/api/workflow/{wf_id}/decision",
            json=approval_payload,
            headers={"Authorization": f"Bearer {MGR_TOKEN}"},
        )
        assert res_app.status_code == 200
        completed_data = res_app.json()
        assert completed_data["status"] == "COMPLETED"
        assert completed_data["approval_record"]["approver_role"] == "manager"
        assert completed_data["execution_record"]["status"] == "SUCCESS"

        # 4. Inspect audit trail
        res_audit = client.get(f"/api/workflow/{wf_id}/audit")
        assert res_audit.status_code == 200
        audit_data = res_audit.json()
        assert audit_data["is_complete"] is True
        assert audit_data["terminal_state"] == "COMPLETED"

    def test_critical_rbac_trust_boundary_role_forgery_rejected(self):
        """
        CRITICAL TEST: An agent submits an approval payload with a forged role ("admin")
        in the request body while authenticated with an agent token.
        System must resolve identity exclusively server-side and REJECT with 403 Forbidden.
        """
        # Start sensitive L2 investigation
        res = client.post(
            "/api/workflow/investigate",
            json={
                "customer_id": "CUST-1002",
                "customer_name": "Arjun Sharma",
                "issue_summary": "Damaged goods reported for fourth time. Escalation required.",
            },
            headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
        )
        wf_id = res.json()["workflow_id"]

        # Support agent attempts to forge 'admin' in body fields
        forged_payload = {
            "decision": "APPROVE",
            "approver_role": "admin",          # Malicious forgery attempt!
            "user_role": "admin",              # Malicious forgery attempt!
            "comments": "Claiming to be admin to bypass approval gate.",
        }
        res_forge = client.post(
            f"/api/workflow/{wf_id}/decision",
            json=forged_payload,
            headers={"Authorization": f"Bearer {AGENT_TOKEN}"},  # Agent token!
        )

        # Non-negotiable security invariant: Must return 403 Forbidden
        assert res_forge.status_code == 403
        detail = res_forge.json()["detail"]
        assert detail["error"] == "RBAC_PERMISSION_DENIED"
        assert detail["user_role"] == "support_agent"  # Server-resolved role preserved!
        assert "Requires Manager or Admin" in detail["message"]
