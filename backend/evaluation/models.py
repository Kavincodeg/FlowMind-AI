"""
FlowMind AI - Evaluation Models & Benchmark Schema (Phase 4)
Defines data structures for benchmark test cases, comparative evaluation metrics,
case execution outcomes, and comparative summary statistics.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RetrievalMetrics(BaseModel):
    """
    Standard information retrieval evaluation metrics.
    """
    model_config = ConfigDict(extra="ignore")

    precision_at_3: float = Field(default=0.0, description="Precision@3: proportion of top-3 retrieved items that are relevant")
    precision_at_5: float = Field(default=0.0, description="Precision@5: proportion of top-5 retrieved items that are relevant")
    recall_at_5: float = Field(default=0.0, description="Recall@5: proportion of relevant items retrieved in top-5")
    mrr: float = Field(default=0.0, description="Mean Reciprocal Rank (MRR) of first relevant item")
    mean_latency_ms: float = Field(default=0.0, description="Mean retrieval query latency in milliseconds")
    total_queries: int = Field(default=0, description="Total number of evaluated retrieval queries")


class FlowMindCaseResult(BaseModel):
    """
    Detailed evaluation outcome of a single test case processed by FlowMind AI.
    """
    model_config = ConfigDict(extra="ignore")

    case_id: str
    category: str
    status: str                         # "COMPLETED" | "AUTO_EXECUTED" | "ABSTAINED" | "REJECTED" | "FAILED"
    action_type: Optional[str] = None
    escalation_level: Optional[str] = None
    target_team: Optional[str] = None

    action_correct: bool = Field(default=False, description="True if recommended action matches ground truth expectations")
    task_success: bool = Field(default=False, description="True if workflow completed its expected lifecycle state without error")
    approval_required: bool = Field(default=False, description="True if action required human approval gating")
    approval_complied: bool = Field(default=True, description="True if approval gating was strictly respected")
    injection_detected: bool = Field(default=False, description="True if prompt injection was detected")
    injection_defended: bool = Field(default=True, description="True if prompt injection was safely neutralized")
    citation_integrity: bool = Field(default=True, description="True if all output citations were grounded in retrieved evidence")

    # NOTE: Audit completeness is strictly evaluated via Phase 3 AuditRecord.is_complete.
    # No unverified SHA-256 chain claim is assumed.
    audit_complete: bool = Field(default=False, description="True if lifecycle produced an audit record meeting is_complete criteria")

    latency_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Timing breakdown: retrieval_ms, reasoning_ms, execution_ms, total_ms",
    )
    error_message: Optional[str] = None


class BaselineCaseResult(BaseModel):
    """
    Detailed evaluation outcome of a single test case processed by the Plain-RAG Baseline.
    """
    model_config = ConfigDict(extra="ignore")

    case_id: str
    category: str
    answer_text: str
    citations_count: int = 0

    action_suggested: bool = Field(default=False, description="True if baseline generated an unstructured action mention")
    action_executed: bool = Field(default=False, description="Always False: baseline has no execution connector")
    approval_gated: bool = Field(default=False, description="Always False: baseline has no approval mechanism")
    audit_trail_created: bool = Field(default=False, description="Always False: baseline has no audit logging")

    latency_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Timing breakdown: retrieval_ms, generation_ms, total_ms",
    )
    error_message: Optional[str] = None


class ComparativeMetricsSummary(BaseModel):
    """
    Comparative performance matrix contrasting FlowMind AI against the Plain-RAG Baseline.
    Captures empirical research findings without predetermined pass/fail thresholds.
    """
    model_config = ConfigDict(extra="ignore")

    total_cases: int
    flowmind_task_success_rate: float
    baseline_task_success_rate: float

    flowmind_action_accuracy: float
    baseline_action_accuracy: float

    flowmind_citation_integrity_rate: float
    baseline_citation_integrity_rate: float

    flowmind_approval_compliance_rate: float
    baseline_approval_compliance_rate: float

    flowmind_injection_defense_rate: float
    baseline_injection_defense_rate: float

    flowmind_audit_completeness_rate: float
    baseline_audit_completeness_rate: float

    flowmind_mean_latency_ms: float
    baseline_mean_latency_ms: float

    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class BenchmarkResult(BaseModel):
    """
    Comprehensive output artifact representing a completed evaluation run.
    """
    model_config = ConfigDict(extra="ignore")

    timestamp: str
    dataset_size: int
    retrieval_metrics: RetrievalMetrics
    comparative_summary: ComparativeMetricsSummary
    flowmind_cases: List[FlowMindCaseResult]
    baseline_cases: List[BaselineCaseResult]
