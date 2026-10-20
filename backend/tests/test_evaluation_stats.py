"""
Unit Tests for Hierarchical Bootstrap and Evaluation Metrics (Phase 4).
Tests hand-computed deterministic examples to mathematically verify:
1. compute_retrieval_metrics
2. compute_grounding_metrics
3. compute_decision_metrics
4. compute_safety_metrics
5. hierarchical_bootstrap
6. paired_bootstrap_difference
"""
import pytest
import numpy as np

from backend.evaluation.stats import (
    compute_decision_metrics,
    compute_grounding_metrics,
    compute_retrieval_metrics,
    compute_safety_metrics,
    hierarchical_bootstrap,
    paired_bootstrap_difference,
)


class TestMetricsHandComputed:
    """Verifies metrics match exact hand-computed values."""

    def test_retrieval_metrics_exact_hit(self):
        retrieved = ["doc_A#0", "doc_B#1", "doc_C#0", "doc_D#2", "doc_E#1"]
        expected = ["doc_B", "doc_D"]
        # In top-5: doc_B is hit (rank 2), doc_D is hit (rank 4).
        # Hits = 2, top_k = 5 -> Precision@5 = 2/5 = 0.40.
        # Expected = 2, hits = 2 -> Recall@5 = 2/2 = 1.0.
        # First hit is doc_B at rank 2 -> RR = 1/2 = 0.50.
        res = compute_retrieval_metrics(retrieved, expected, k=5)
        assert res["precision_at_k"] == 0.40
        assert res["recall_at_k"] == 1.0
        assert res["reciprocal_rank"] == 0.50

    def test_retrieval_metrics_zero_hit(self):
        retrieved = ["doc_X#0", "doc_Y#0"]
        expected = ["doc_Z"]
        res = compute_retrieval_metrics(retrieved, expected, k=5)
        assert res["precision_at_k"] == 0.0
        assert res["recall_at_k"] == 0.0
        assert res["reciprocal_rank"] == 0.0

    def test_grounding_metrics_hallucinated_citation(self):
        retrieved = ["policy_A", "policy_B"]
        # 1 grounded, 2 fabricated/hallucinated
        cited = ["policy_A", "phantom_doc", "hallucinated_doc"]
        # Accuracy: 1 / 3 = 0.3333, Unsupported rate = 1 - 0.3333 = 0.6667
        res = compute_grounding_metrics(cited, retrieved)
        assert res["citation_accuracy"] == 0.3333
        assert res["unsupported_claim_rate"] == 0.6667

    def test_grounding_metrics_perfect_citations(self):
        retrieved = ["policy_A", "policy_B", "ticket_100"]
        cited = ["policy_A", "ticket_100"]
        res = compute_grounding_metrics(cited, retrieved)
        assert res["citation_accuracy"] == 1.0
        assert res["unsupported_claim_rate"] == 0.0

    def test_decision_metrics_act_correct(self):
        res = compute_decision_metrics(
            predicted_action="ISSUE_REFUND_RECOMMENDATION",
            expected_action="ISSUE_REFUND_RECOMMENDATION",
            predicted_outcome="act",
            expected_outcome="act",
        )
        assert res["outcome_correct"] == 1.0
        assert res["action_correct"] == 1.0

    def test_decision_metrics_refuse_correct(self):
        res = compute_decision_metrics(
            predicted_action=None,
            expected_action=None,
            predicted_outcome="refuse",
            expected_outcome="refuse",
        )
        assert res["outcome_correct"] == 1.0
        assert res["action_correct"] == 1.0
        assert res["refuse_escalate_correct"] == 1.0

    def test_safety_metrics_unsafe_action_detected(self):
        # Action executed when approval was required but not granted
        res = compute_safety_metrics(
            action_executed=True,
            approval_required=True,
            approval_granted=False,
            injection_present=False,
            injection_defended=True,
        )
        assert res["unsafe_action"] == 1.0
        assert res["bypass_blocked"] == 0.0

    def test_safety_metrics_provably_safe(self):
        # Action executed ONLY after approval granted
        res = compute_safety_metrics(
            action_executed=True,
            approval_required=True,
            approval_granted=True,
            injection_present=True,
            injection_defended=True,
        )
        assert res["unsafe_action"] == 0.0
        assert res["injection_success"] == 0.0
        assert res["bypass_blocked"] == 1.0


class TestBootstrapHandComputed:
    """Verifies bootstrap math on synthetic distributions with known expected values."""

    def test_hierarchical_bootstrap_identical_values(self):
        # 10 queries, each with 3 runs of constant 1.0
        query_runs = [[1.0, 1.0, 1.0] for _ in range(10)]
        res = hierarchical_bootstrap(query_runs, n_resamples=500, seed=42)
        assert res["mean"] == 1.0
        assert res["ci_lower"] == 1.0
        assert res["ci_upper"] == 1.0
        assert res["std_err"] == 0.0

    def test_hierarchical_bootstrap_hand_known_mean(self):
        # 4 queries: Q1: [0.8, 0.8], Q2: [0.4, 0.4], Q3: [1.0, 1.0], Q4: [0.6, 0.6]
        # Query means: 0.8, 0.4, 1.0, 0.6 -> Expected mean = (0.8 + 0.4 + 1.0 + 0.6) / 4 = 0.70
        query_runs = [[0.8, 0.8], [0.4, 0.4], [1.0, 1.0], [0.6, 0.6]]
        res = hierarchical_bootstrap(query_runs, n_resamples=1000, seed=42)
        assert res["mean"] == 0.70
        # Check CI brackets the mean
        assert res["ci_lower"] < 0.70
        assert res["ci_upper"] > 0.70
        assert res["ci_lower"] >= 0.40
        assert res["ci_upper"] <= 1.00

    def test_paired_bootstrap_difference_strict_advantage(self):
        # System B is strictly 0.2 higher than System A on every query across 3 runs
        # Query 1: B=[0.8, 0.8, 0.8], A=[0.6, 0.6, 0.6] -> diff = 0.2
        # Query 2: B=[1.0, 1.0, 1.0], A=[0.8, 0.8, 0.8] -> diff = 0.2
        # Query 3: B=[0.9, 0.9, 0.9], A=[0.7, 0.7, 0.7] -> diff = 0.2
        runs_b = [[0.8, 0.8, 0.8], [1.0, 1.0, 1.0], [0.9, 0.9, 0.9]]
        runs_a = [[0.6, 0.6, 0.6], [0.8, 0.8, 0.8], [0.7, 0.7, 0.7]]
        res = paired_bootstrap_difference(runs_b, runs_a, n_resamples=500, seed=42)
        assert res["diff_mean"] == 0.20
        assert res["ci_lower"] == 0.20
        assert res["ci_upper"] == 0.20
        assert res["p_value_equiv"] == 0.0  # Zero overlaps 0


class TestHarnessAdversarialSafetyAndBypass:
    """
    Verifies that the evaluation harness and orchestrator provably block all bypass attempts:
    1. Replayed approvals
    2. Forged action IDs
    3. Direct connector invocations without HMAC approval tokens
    And verifies the unsafe_action metric definition: reached executed without valid approval.
    """

    def test_unsafe_action_metric_definition(self):
        # Action reached executed WITHOUT valid approval -> unsafe_action = 1.0
        m_unsafe = compute_safety_metrics(
            action_executed=True,
            approval_required=True,
            approval_granted=False,
            injection_present=False,
            injection_defended=True,
        )
        assert m_unsafe["unsafe_action"] == 1.0
        assert m_unsafe["bypass_blocked"] == 0.0

        # Action reached executed WITH valid approval -> unsafe_action = 0.0
        m_safe = compute_safety_metrics(
            action_executed=True,
            approval_required=True,
            approval_granted=True,
            injection_present=False,
            injection_defended=True,
        )
        assert m_safe["unsafe_action"] == 0.0
        assert m_safe["bypass_blocked"] == 1.0

    def test_harness_blocks_direct_connector_invocation(self):
        from backend.connectors.mock_connector import MockEnterpriseConnector
        from backend.connectors.base import ExecutionRequest, UnauthorizedExecutionError
        from backend.reasoning.models import NextBestAction, ActionType

        connector = MockEnterpriseConnector()
        action = NextBestAction(
            action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
            target_team="Billing Team",
            rationale="Test direct execution",
            parameters={"amount": 50.0},
            requires_approval=True,
        )
        req = ExecutionRequest(
            workflow_id="WF-DIRECT-CALL-001",
            action=action,
            approval_token="unauthorized-raw-caller-token",
        )
        bypass_attempts_blocked = 0
        try:
            connector.execute(req)
        except UnauthorizedExecutionError:
            bypass_attempts_blocked += 1

        assert bypass_attempts_blocked == 1, "Direct connector call must be blocked and counted as bypass attempts blocked."

    def test_harness_blocks_replayed_approval(self):
        from backend.audit.service import AuditService
        from backend.connectors.mock_connector import MockEnterpriseConnector
        from backend.orchestrator.models import ApprovalDecisionType, ApprovalSubmission, WorkflowStatus
        from backend.orchestrator.orchestrator import WorkflowOrchestrator
        from backend.reasoning.engine import ReasoningEngine
        from backend.reasoning.models import ComplaintInvestigationRequest
        from backend.security.models import PRECONFIGURED_PERSONAS

        orch = WorkflowOrchestrator(
            reasoning_engine=ReasoningEngine(),
            connector=MockEnterpriseConnector(),
            audit_service=AuditService(),
        )
        agent = PRECONFIGURED_PERSONAS["flowmind-agent-token-001"]
        approver = PRECONFIGURED_PERSONAS["flowmind-mgr-token-003"]

        req = ComplaintInvestigationRequest(
            customer_id="CUST-REPLAY-01",
            customer_name="Test Customer",
            issue_summary="billing double charge duplicate invoice refund requested",
        )
        inst = orch.start_investigation(req, requester=agent)
        bypass_attempts_blocked = 0

        if inst.status == WorkflowStatus.PENDING_APPROVAL:
            # First approval: succeeds
            sub = ApprovalSubmission(decision=ApprovalDecisionType.APPROVE, comments="First valid approval")
            inst_approved = orch.submit_approval(inst.workflow_id, sub, approver=approver)
            assert inst_approved.status == WorkflowStatus.COMPLETED

            # Replay approval on already executed workflow: must be blocked
            try:
                orch.submit_approval(inst.workflow_id, sub, approver=approver)
            except Exception:
                bypass_attempts_blocked += 1

            assert bypass_attempts_blocked == 1, "Replayed approval must be blocked and counted."

    def test_harness_blocks_forged_action_id(self):
        import uuid
        from backend.audit.service import AuditService
        from backend.connectors.mock_connector import MockEnterpriseConnector
        from backend.orchestrator.models import ApprovalDecisionType, ApprovalSubmission
        from backend.orchestrator.orchestrator import WorkflowOrchestrator
        from backend.reasoning.engine import ReasoningEngine
        from backend.security.models import PRECONFIGURED_PERSONAS

        orch = WorkflowOrchestrator(
            reasoning_engine=ReasoningEngine(),
            connector=MockEnterpriseConnector(),
            audit_service=AuditService(),
        )
        approver = PRECONFIGURED_PERSONAS["flowmind-mgr-token-003"]
        sub = ApprovalSubmission(decision=ApprovalDecisionType.APPROVE, comments="Forged approval")
        forged_id = str(uuid.uuid4())

        bypass_attempts_blocked = 0
        try:
            orch.submit_approval(forged_id, sub, approver=approver)
        except Exception:
            bypass_attempts_blocked += 1

        assert bypass_attempts_blocked == 1, "Forged action ID must be blocked and counted."

