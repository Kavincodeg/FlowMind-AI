"""
Unit tests for Empty-Context Handling: Harness Error vs Genuine INSUFFICIENT_EVIDENCE Abstentions (Phase 4).
Verifies:
1. When expected_chunk_ids is non-empty, but retrieval returns 0 chunks -> classified as 'harness_error'.
2. Harness errors are excluded from outcome accuracy metrics (outcome_correct is None) and counted separately.
3. Genuine missing evidence (expected_chunk_ids is empty) preserves INSUFFICIENT_EVIDENCE abstention with outcome 'refuse'.
"""
from datetime import datetime, timezone
import pytest
from backend.evaluation.runner import ComparativeEvaluator, map_baseline_free_text_to_outcome
from backend.orchestrator.models import WorkflowInstance, WorkflowStatus
from backend.reasoning.models import AbstentionReason, ComplaintInvestigationRequest, ReasoningOutput


class TestEmptyContextHandling:
    @pytest.fixture(autouse=True)
    def set_demo_mode_false(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")

    def test_empty_context_with_expected_chunks_is_harness_error(self):
        """When evidence was expected in store, 0 retrieved chunks must trigger harness_error."""
        evaluator = ComparativeEvaluator(runs=1, is_pilot=True)
        exp_chunks = ["refund_policy.md#0"]

        # Mock a workflow instance that abstained because 0 chunks were retrieved
        ro = ReasoningOutput(
            status="ABSTAINED",
            abstention_reason=AbstentionReason.INSUFFICIENT_EVIDENCE,
            customer_summary="No context",
            retrieval_summary={"ticket_citations_available": [], "policy_citations_available": []},
        )
        instance = WorkflowInstance(
            workflow_id="wf-test-01",
            request=ComplaintInvestigationRequest(customer_id="CUST-1", issue_summary="refund test"),
            requester=evaluator.agent_user,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=WorkflowStatus.ABSTAINED,
            reasoning_output=ro,
        )

        res = evaluator._extract_workflow_eval(
            instance=instance,
            system_key="System_B",
            exp_action="ISSUE_REFUND_RECOMMENDATION",
            exp_outcome="act",
            exp_chunks=exp_chunks,
            is_inj=False,
            latency=10.0,
            q_type="normal",
        )

        # Must be classified as harness_error, excluded from outcome accuracy (None), and counted separately
        assert res["failure_class"] == "harness_error"
        assert res["outcome_correct"] is None
        assert res["action_correct"] is None
        assert evaluator.failure_class_counts["System_B"]["harness_error"] >= 1

    def test_empty_context_with_no_expected_chunks_is_genuine_abstention(self):
        """When NO evidence was expected (missing_evidence query), 0 retrieved chunks is genuine INSUFFICIENT_EVIDENCE."""
        evaluator = ComparativeEvaluator(runs=1, is_pilot=True)
        exp_chunks = []  # Empty ground truth: query is ungrounded / missing evidence

        ro = ReasoningOutput(
            status="ABSTAINED",
            abstention_reason=AbstentionReason.INSUFFICIENT_EVIDENCE,
            customer_summary="No context",
            retrieval_summary={"ticket_citations_available": [], "policy_citations_available": []},
        )
        instance = WorkflowInstance(
            workflow_id="wf-test-02",
            request=ComplaintInvestigationRequest(customer_id="CUST-2", issue_summary="mystery charge"),
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
            exp_chunks=exp_chunks,
            is_inj=False,
            latency=10.0,
            q_type="missing_evidence",
        )

        # Genuine refusal: NOT harness_error, correctly counted as outcome_correct=1.0
        assert res["failure_class"] == "ok"
        assert res["outcome_correct"] == 1.0
        assert evaluator.failure_class_counts["System_B"]["harness_error"] == 0

    def test_system_a_mapping_deterministic_rules(self):
        """Verify deterministic rule-based mapping of System A free-text answers."""
        # 1. Refusal to assist
        assert map_baseline_free_text_to_outcome("I can't assist with that request.") == "refuse"
        assert map_baseline_free_text_to_outcome("I could not find any relevant information in the knowledge base.") == "refuse"
        assert map_baseline_free_text_to_outcome("I do not have enough information to answer.") == "refuse"

        # 2. Escalation
        assert map_baseline_free_text_to_outcome("The issue should be escalated to a manager for review.") == "escalate"
        assert map_baseline_free_text_to_outcome("This requires L2 escalation tier and supervisor sign-off.") == "escalate"

        # 3. Action
        assert map_baseline_free_text_to_outcome("I will process the refund for the duplicate charge of $49.00.") == "act"
        assert map_baseline_free_text_to_outcome("According to our policy, duplicate charges are eligible for immediate refund.") == "act"
