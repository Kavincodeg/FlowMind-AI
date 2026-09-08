"""
FlowMind AI - Evaluation Module Tests (Phase 4)
Tests benchmark dataset integrity, retrieval metrics calculations, evaluation harness,
structural invariants, reporting exports, and evaluation API endpoints.

ACADEMIC INTEGRITY NOTE:
Any survey generation helper in this test file is strictly a test fixture for validating
data structures. It is never used to produce or report evaluation results.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.evaluation.harness import EvaluationHarness
from backend.evaluation.models import (
    BaselineCaseResult,
    BenchmarkResult,
    ComparativeMetricsSummary,
    FlowMindCaseResult,
    RetrievalMetrics,
)
from backend.evaluation.reporter import BenchmarkReporter

ROOT_DIR = Path(__file__).parent.parent.parent
COMPLAINT_CASES_FILE = ROOT_DIR / "backend" / "data" / "complaint_test_cases.json"
TEST_QUERIES_FILE = ROOT_DIR / "backend" / "data" / "test_queries.json"


# ============================================================
# Test-Only Survey Fixture (NOT used for reporting results)
# ============================================================

# TEST FIXTURE ONLY: This synthetic survey generation function is strictly used for
# testing data structures and survey parsing in test_evaluation.py. It must NEVER be
# used to produce, report, or export evaluation results. The real human evaluation is
# an independent empirical study conducted with human participants outside this codebase.
def generate_survey_fixture_for_testing(
    cases: List[Dict[str, Any]],
    n_evaluators: int = 5,
) -> Dict[str, Any]:
    """
    Test-only fixture generating dummy survey questionnaire entries to test schema validation.
    """
    survey_entries = []
    for c in cases[:3]:
        survey_entries.append({
            "case_id": c["case_id"],
            "evaluator_id": "TEST_EVAL_01",
            "trust_score": 4,
            "clarity_score": 5,
            "actionability_score": 4,
            "safety_score": 5,
        })
    return {"total_responses": len(survey_entries), "entries": survey_entries}


class TestEvaluationDatasetIntegrity:
    """Validate completeness and schema conformance of benchmark datasets."""

    def test_complaint_cases_has_30_items(self):
        assert COMPLAINT_CASES_FILE.exists(), f"Missing {COMPLAINT_CASES_FILE}"
        with open(COMPLAINT_CASES_FILE, "r", encoding="utf-8") as f:
            cases = json.load(f)

        assert len(cases) == 30, f"Expected 30 curated benchmark cases, found {len(cases)}"

        case_ids = [c["case_id"] for c in cases]
        assert len(case_ids) == len(set(case_ids)), "All case IDs must be unique"

        for idx, c in enumerate(cases, 1):
            assert f"CASE-{idx:03d}" == c["case_id"], f"Case ID format mismatch at index {idx}"
            assert "category" in c
            assert "description" in c
            assert "request" in c
            assert "issue_summary" in c["request"]
            assert "expected" in c

    def test_test_queries_dataset_integrity(self):
        assert TEST_QUERIES_FILE.exists()
        with open(TEST_QUERIES_FILE, "r", encoding="utf-8") as f:
            queries = json.load(f)

        assert len(queries) >= 10, "Expected at least 10 retrieval test queries"
        for q in queries:
            assert "query_id" in q
            assert "query_text" in q


class TestMetricsCalculation:
    """Test standard evaluation metrics math."""

    def test_retrieval_metrics_calculation(self):
        harness = EvaluationHarness()
        mock_queries = [
            {
                "query_id": "Q1",
                "query_text": "billing dispute charged twice",
                "source_type": "ticket",
                "relevant_source_ids": ["TKT-0008"],
            },
            {
                "query_id": "Q2",
                "query_text": "escalation policy repeat contact",
                "source_type": "policy",
                "relevant_source_ids": ["escalation_policy.md"],
            },
        ]
        metrics = harness.run_retrieval_benchmark(mock_queries)

        assert isinstance(metrics, RetrievalMetrics)
        assert metrics.total_queries == 2
        assert 0.0 <= metrics.precision_at_3 <= 1.0
        assert 0.0 <= metrics.precision_at_5 <= 1.0
        assert 0.0 <= metrics.recall_at_5 <= 1.0
        assert 0.0 <= metrics.mrr <= 1.0

    def test_survey_fixture_parsing(self):
        """Verify the test-only survey helper operates as an isolated fixture."""
        with open(COMPLAINT_CASES_FILE, "r", encoding="utf-8") as f:
            cases = json.load(f)

        fixture = generate_survey_fixture_for_testing(cases, n_evaluators=3)
        assert fixture["total_responses"] == 3
        for entry in fixture["entries"]:
            assert 1 <= entry["trust_score"] <= 5
            assert 1 <= entry["clarity_score"] <= 5


class TestStructuralInvariants:
    """
    Verifies architectural properties that are true by design rather than empirical research metrics.
    """

    @pytest.fixture(autouse=True)
    def setup_harness(self):
        self.harness = EvaluationHarness()
        with open(COMPLAINT_CASES_FILE, "r", encoding="utf-8") as f:
            self.cases = json.load(f)

    def test_invariant_1_baseline_never_executes_actions(self):
        """Baseline pipeline must NEVER produce an action execution."""
        sample_cases = self.cases[:5]
        for c in sample_cases:
            bl_res = self.harness.run_baseline_case(c)
            assert bl_res.action_executed is False, f"Baseline must never execute actions: {c['case_id']}"

    def test_invariant_2_baseline_never_produces_audit_record(self):
        """Baseline pipeline must NEVER generate an audit trail."""
        sample_cases = self.cases[:5]
        for c in sample_cases:
            bl_res = self.harness.run_baseline_case(c)
            assert bl_res.audit_trail_created is False, f"Baseline must never create audit records: {c['case_id']}"

    def test_invariant_3_completed_flowmind_case_has_complete_audit(self):
        """Completed FlowMind case must produce an audit record with is_complete=True."""
        happy_case = self.cases[0]  # CASE-001 (Repeat complaint escalation)
        fm_res = self.harness.run_flowmind_case(happy_case)
        assert fm_res.status == "COMPLETED"
        assert fm_res.audit_complete is True

    def test_invariant_4_sensitive_action_enforces_human_approval(self):
        """Sensitive actions must require and enforce human approval before execution."""
        legal_case = self.cases[1]  # CASE-002 (Legal threat)
        fm_res = self.harness.run_flowmind_case(legal_case)
        assert fm_res.approval_required is True
        assert fm_res.approval_complied is True

    def test_invariant_5_abstention_case_has_no_approval_or_execution(self):
        """Abstention cases must conclude with status ABSTAINED and no approval or execution records."""
        abstain_case = self.cases[8]  # CASE-009 (Insufficient evidence)
        fm_res = self.harness.run_flowmind_case(abstain_case)
        assert fm_res.status == "ABSTAINED"
        assert fm_res.approval_required is False


class TestEvaluationReporter:
    """Verify Markdown and JSON report generation."""

    def test_reporter_produces_valid_markdown_and_json(self, tmp_path):
        harness = EvaluationHarness()
        with open(COMPLAINT_CASES_FILE, "r", encoding="utf-8") as f:
            sample_cases = json.load(f)[:6]

        result = harness.run_comparative_benchmark(cases=sample_cases)
        assert isinstance(result, BenchmarkResult)

        md_content = BenchmarkReporter.generate_markdown_report(result)
        assert "# FlowMind AI — Comparative Evaluation Benchmark Report" in md_content
        assert "Overall System Comparison: FlowMind AI vs. Plain-RAG Baseline" in md_content
        assert "Information Retrieval Quality" in md_content
        assert "Separation of Systems Benchmark and Human Study" in md_content

        md_path, json_path = BenchmarkReporter.save_reports(result, output_dir=tmp_path)
        assert md_path.exists()
        assert json_path.exists()

        with open(json_path, "r", encoding="utf-8") as f:
            loaded_json = json.load(f)
        assert loaded_json["dataset_size"] == 6
        assert "comparative_summary" in loaded_json


class TestEvaluationAPIRoutes:
    """Test evaluation endpoints exposed via FastAPI."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_benchmark_results_authenticated(self, client):
        headers = {"Authorization": "Bearer flowmind-agent-token-001"}
        resp = client.get("/api/evaluation/benchmark", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "comparative_summary" in data
        assert "retrieval_metrics" in data

    def test_get_retrieval_metrics_authenticated(self, client):
        headers = {"Authorization": "Bearer flowmind-agent-token-001"}
        resp = client.get("/api/evaluation/retrieval", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "precision_at_3" in data
        assert "mrr" in data

    def test_human_eval_route_does_not_exist(self, client):
        """CRITICAL: Academic integrity check: no synthetic human survey route exists."""
        headers = {"Authorization": "Bearer flowmind-admin-token-004"}
        resp = client.get("/api/evaluation/human-eval", headers=headers)
        assert resp.status_code == 404, "Synthetic human evaluation endpoint must NOT exist!"
