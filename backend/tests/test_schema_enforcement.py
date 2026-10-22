"""
Unit tests for Schema Enforcement and Format Failure Exclusion (Phase 4).
Verifies:
1. Missing or malformed required fields (e.g., confidence_score, status) produce
   schema_deviation/parse_failure errors, NOT LOW_CONFIDENCE abstentions.
2. Format/schema failures are excluded from outcome accuracy (outcome_correct = None)
   and never score as correct refusals.
3. Genuine LOW_CONFIDENCE / INSUFFICIENT_EVIDENCE abstentions that conform to schema
   are classified as 'ok' and scored normally against expected outcomes.
"""
import json
from datetime import datetime, timezone
import pytest

from backend.evaluation.runner import ComparativeEvaluator
from backend.orchestrator.models import WorkflowInstance, WorkflowStatus
from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.llm_provider import MockLLMProvider
from backend.reasoning.models import AbstentionReason, ComplaintInvestigationRequest, ReasoningOutput


class TestSchemaEnforcement:
    @pytest.fixture(autouse=True)
    def set_demo_mode_false(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")

    def test_missing_confidence_score_is_schema_deviation_not_low_confidence(self):
        """Missing confidence_score must raise schema_deviation and not force LOW_CONFIDENCE abstention."""
        engine = ReasoningEngine()
        
        # Test JSON missing confidence_score
        bad_json = json.dumps({
            "status": "RECOMMENDATION_READY",
            "customer_summary": "Customer inquiry",
            "identified_root_cause": "Issue identified",
            "rationale": "Valid rationale",
        })

        with pytest.raises(ValueError) as excinfo:
            engine._parse_and_validate_json(bad_json)
        assert "confidence_score" in str(excinfo.value)
        assert "schema_deviation" in str(excinfo.value)

    def test_invalid_status_is_schema_deviation(self):
        """Unrecognized status must trigger schema_deviation."""
        engine = ReasoningEngine()
        bad_json = json.dumps({
            "status": "ACTIONABLE",  # Invalid non-schema status
            "confidence_score": 0.85,
        })
        with pytest.raises(ValueError) as excinfo:
            engine._parse_and_validate_json(bad_json)
        assert "status" in str(excinfo.value)
        assert "schema_deviation" in str(excinfo.value)

    def test_schema_deviation_excluded_from_outcome_correctness(self):
        """Direction 1: A schema_deviation must have outcome_correct = None and never score as correct refusal."""
        evaluator = ComparativeEvaluator(runs=1, is_pilot=True)
        
        # Simulate a failed reasoning output due to schema deviation
        ro = ReasoningOutput(
            status="ERROR",
            abstention_reason=None,
            customer_summary="Error parsing model response.",
            identified_root_cause="schema_deviation: Missing required field 'confidence_score'",
            rationale="Model did not return valid JSON adhering to schema",
            confidence_score=0.0,
        )
        instance = WorkflowInstance(
            workflow_id="wf-schema-dev-01",
            request=ComplaintInvestigationRequest(customer_id="CUST-1", issue_summary="missing evidence complaint"),
            requester=evaluator.agent_user,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=WorkflowStatus.FAILED,
            reasoning_output=ro,
        )

        # Even if expected outcome is 'refuse', schema failure must NOT score as correct refusal
        res = evaluator._extract_workflow_eval(
            instance=instance,
            system_key="System_B",
            exp_action=None,
            exp_outcome="refuse",
            exp_chunks=[],
            is_inj=False,
            latency=15.0,
            q_type="missing_evidence",
        )

        assert res["failure_class"] == "schema_deviation"
        assert res["outcome_correct"] is None  # Excluded from outcome accuracy
        assert res["action_correct"] is None
        assert evaluator.failure_class_counts["System_B"]["schema_deviation"] >= 1

    def test_genuine_low_confidence_refusal_is_scored_normally(self):
        """Direction 2: Valid schema with explicit LOW_CONFIDENCE abstention scores normally."""
        evaluator = ComparativeEvaluator(runs=1, is_pilot=True)
        
        # Valid schema abstention
        ro = ReasoningOutput(
            status="ABSTAINED",
            abstention_reason=AbstentionReason.LOW_CONFIDENCE,
            customer_summary="Ambiguous complaint details",
            identified_root_cause="Uncertain transaction origin",
            rationale="Confidence below enterprise threshold",
            confidence_score=0.35,
        )
        instance = WorkflowInstance(
            workflow_id="wf-valid-refusal-01",
            request=ComplaintInvestigationRequest(customer_id="CUST-1", issue_summary="low confidence case"),
            requester=evaluator.agent_user,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=WorkflowStatus.ABSTAINED,
            reasoning_output=ro,
        )

        res = evaluator._extract_workflow_eval(
            instance=instance,
            system_key="System_B",
            exp_action=None,
            exp_outcome="refuse",
            exp_chunks=[],
            is_inj=False,
            latency=15.0,
            q_type="missing_evidence",
        )

        # Genuine refusal must be ok failure_class and score outcome_correct = 1.0
        assert res["failure_class"] == "ok"
        assert res["outcome_correct"] == 1.0
        assert res["refuse_escalate_correct"] == 1.0
