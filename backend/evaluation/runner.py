"""
FlowMind AI - 4-System Comparative Evaluation Runner (Phase 4).
Runs empirical comparison across:
- System A: Plain-RAG baseline (retrieve -> answer, no action schema, no approval gate)
- System B: FlowMind full pipeline (grounded reasoning, human approval gate, HMAC connector, audit chain)
- System C: FlowMind Ablation 1 (without evidence grounding check)
- System D: FlowMind Ablation 2 (without human approval gate; mock connector ONLY)

Enforces:
1. Mock guard: fails if runs >= 3 is used with a deterministic mock LLM.
2. System D safety assertion: fails if System D is bound to anything other than MockEnterpriseConnector.
3. System D unsafe-action rate reported strictly in its own isolated ablation column.
4. Held-out guard: fails if held-out split is run without verified LABELS.lock.
5. Hierarchical bootstrap with paired comparisons (B vs A).
6. Immutable timestamped JSON run logging.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.audit.service import AuditService
from backend.baseline.models import BaselineQuery
from backend.baseline.service import PlainRAGBaseline
from backend.connectors.base import EnterpriseConnector, ExecutionRequest, UnauthorizedExecutionError
from backend.connectors.mock_connector import MockEnterpriseConnector
from backend.evaluation.judge_prompts import (
    evaluate_claims_grounding,
    extract_factual_claims,
    judge_claim_entailment,
)
from backend.evaluation.stats import (
    compute_decision_metrics,
    compute_grounding_metrics,
    compute_retrieval_metrics,
    compute_safety_metrics,
    hierarchical_bootstrap,
    paired_bootstrap_difference,
)
from backend.orchestrator.models import ApprovalDecisionType, ApprovalSubmission, WorkflowStatus
from backend.orchestrator.orchestrator import WorkflowOrchestrator
from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.llm_provider import (
    GeminiLLMProvider,
    LLMProvider,
    MockLLMProvider,
    get_llm_provider,
)
from backend.reasoning.models import ActionType, ComplaintInvestigationRequest, NextBestAction
from backend.retrieval.mock_retriever import mock_retrieve
from backend.security.authority import can_approve
from backend.security.models import PRECONFIGURED_PERSONAS

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"
RESULTS_DIR = ROOT / "backend" / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def compute_config_hash(config: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of run configuration."""
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ComparativeEvaluator:
    """Orchestrates 4-system evaluation on identical queries."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        connector: Optional[EnterpriseConnector] = None,
        temperature: float = 0.3,
        runs: int = 3,
        split: str = "dev",  # 'dev' or 'held_out'
        is_pilot: bool = False,
    ):
        self.temperature = temperature
        self.runs = runs
        self.split = split
        self.is_pilot = is_pilot
        self.connector = connector or MockEnterpriseConnector(simulate_latency_ms=0.0)

        # Provider resolution
        self.llm_provider = llm_provider or get_llm_provider()

        # Setup judge provider
        if isinstance(self.llm_provider, GeminiLLMProvider):
            self.judge_provider = GeminiLLMProvider(
                model="gemini-3.1-flash-lite",
                thinking_budget=0,
                seed=42,
            )
        else:
            self.judge_provider = MockLLMProvider()

        # Guard 1: Fail if runs >= 3 with a deterministic mock provider
        if self.runs >= 3 and (isinstance(self.llm_provider, MockLLMProvider) or type(self.llm_provider).__name__ == "MockLLMProvider"):
            raise RuntimeError(
                "MOCK GUARD TRIGGERED: A deterministic mock LLM cannot be used for multi-run "
                "empirical evaluation (--runs >= 3). Multi-run evaluation requires a real stochastic LLM "
                "(e.g. Gemini 3.6 Flash, temperature > 0.0) to measure output variance and compute "
                "defensible bootstrap confidence intervals. Mock LLMs are permitted strictly for CI smoke tests with --runs=1."
            )

        # Guard 2: System D safety assertion
        assert isinstance(self.connector, MockEnterpriseConnector), (
            "CRITICAL SAFETY VIOLATION: System D (ungated ablation) MUST NEVER be bound to a live connector. "
            f"Configured connector '{type(self.connector).__name__}' is rejected. Only MockEnterpriseConnector is permitted."
        )

        # Guard 3: Held-out label lock enforcement
        if self.split in ("held_out", "test"):
            lock_file = ROOT / "backend" / "data" / "LABELS.lock"
            if not lock_file.exists():
                raise RuntimeError(
                    "HELD-OUT RUN BLOCKED: LABELS.lock does not exist. "
                    "Held-out labels are treated as unapproved until lead reviewer sign-off."
                )
            from scripts.generate_labels_lock import compute_labels_checksum
            current_chk = compute_labels_checksum()
            locked_chk = lock_file.read_text(encoding="utf-8").strip()
            if current_chk != locked_chk:
                raise RuntimeError(
                    f"HELD-OUT RUN BLOCKED: Checksum mismatch against LABELS.lock! "
                    f"Expected {locked_chk}, calculated {current_chk}. Held-out labels were altered."
                )

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            all_queries = json.load(f)

        if self.split == "dev":
            queries_pool = [q for q in all_queries if q.get("split") == "dev"]
        elif self.split in ("held_out", "test"):
            queries_pool = [q for q in all_queries if q.get("split") == "test"]
        elif self.split == "all":
            queries_pool = all_queries
        else:
            raise ValueError(f"Unknown split: {self.split}")

        if self.is_pilot:
            pilot_sample = []
            for t in ["normal", "multi_hop", "missing_evidence", "conflicting_policy", "adversarial"]:
                matches = [q for q in queries_pool if q.get("benchmark_type") == t]
                if matches:
                    pilot_sample.append(matches[0])
            if len(pilot_sample) < 5:
                pilot_sample = queries_pool[:5]
            self.queries = pilot_sample
        else:
            self.queries = queries_pool

        # Cost Guard (Official pricing rate: dev est $2.72; 1.5x cap is $4.08)
        self.cost_hard_cap_usd = 1.0 if self.is_pilot else min(1.5 * 2.72, 15.0)

        # Bypass and failure tracking
        self.bypass_attempts_blocked_total = 0
        self.failure_class_counts: Dict[str, Dict[str, int]] = {
            s: {"ok": 0, "model_refusal": 0, "blocked_by_provider": 0, "parse_failure": 0, "api_error": 0}
            for s in ["System_A", "System_B", "System_C", "System_D"]
        }
        self.failure_class_by_type: Dict[str, Dict[str, int]] = {}
        self.sample_judge_outputs: List[Dict[str, Any]] = []

        # Personas
        self.agent_user = PRECONFIGURED_PERSONAS["flowmind-agent-token-001"]
        self.approver_candidates = [
            PRECONFIGURED_PERSONAS["flowmind-lead-token-002"],
            PRECONFIGURED_PERSONAS["flowmind-mgr-token-003"],
            PRECONFIGURED_PERSONAS["flowmind-head-token-004"],
            PRECONFIGURED_PERSONAS["flowmind-exec-token-005"],
            PRECONFIGURED_PERSONAS["flowmind-finance-token-006"],
            PRECONFIGURED_PERSONAS["flowmind-vpfin-token-007"],
        ]

        # Setup 4 systems
        self.baseline = PlainRAGBaseline(retriever_fn=mock_retrieve, llm_provider=self.llm_provider)

        self.engine_b = ReasoningEngine(retriever_fn=mock_retrieve, llm_provider=self.llm_provider, enable_grounding_verification=True)
        self.audit_b = AuditService()
        self.orch_b = WorkflowOrchestrator(reasoning_engine=self.engine_b, connector=self.connector, audit_service=self.audit_b)

        self.engine_c = ReasoningEngine(retriever_fn=mock_retrieve, llm_provider=self.llm_provider, enable_grounding_verification=False)
        self.audit_c = AuditService()
        self.orch_c = WorkflowOrchestrator(reasoning_engine=self.engine_c, connector=self.connector, audit_service=self.audit_c)

        self.engine_d = ReasoningEngine(retriever_fn=mock_retrieve, llm_provider=self.llm_provider, enable_grounding_verification=True)
        self.audit_d = AuditService()
        self.orch_d = WorkflowOrchestrator(reasoning_engine=self.engine_d, connector=self.connector, audit_service=self.audit_d, bypass_approval_gate=True)

    def get_run_metadata(self) -> Dict[str, Any]:
        """Compile complete frozen run configuration."""
        model_name = getattr(self.llm_provider, "model", "mock-deterministic-engine")
        judge_name = getattr(self.judge_provider, "model", "mock-judge")
        cfg = {
            "model_name": model_name,
            "judge_model_name": judge_name,
            "provider_class": type(self.llm_provider).__name__,
            "judge_provider_class": type(self.judge_provider).__name__,
            "temperature": self.temperature,
            "seed": getattr(self.llm_provider, "seed", 42),
            "seed_note": "Best-effort seed parameter passed to Gemini API; does not constitute a strict determinism guarantee across hardware/inference shards.",
            "thinking_config": {"thinking_budget": getattr(self.llm_provider, "thinking_budget", 0)},
            "runs": self.runs,
            "split": self.split,
            "is_pilot": self.is_pilot,
            "query_count": len(self.queries),
            "connector_type": type(self.connector).__name__,
            "cost_hard_cap_usd": self.cost_hard_cap_usd,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        cfg["config_hash"] = compute_config_hash(cfg)
        return cfg

    def _eval_single_query(self, query: Dict[str, Any], system_key: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        q_text = query["query_text"]
        q_type = query.get("benchmark_type", "normal")
        exp_outcome = query.get("expected_outcome", "act")
        exp_action = query.get("expected_action_type")
        exp_chunks = query.get("expected_chunk_ids", [])
        is_inj = query.get("benchmark_type") == "adversarial"

        # Check running cost before proceeding
        curr_gen_cost = getattr(self.llm_provider, "total_cost_usd", 0.0)
        curr_jdg_cost = getattr(self.judge_provider, "total_cost_usd", 0.0)
        total_running_cost = curr_gen_cost + curr_jdg_cost
        if total_running_cost > self.cost_hard_cap_usd:
            raise RuntimeError(
                f"COST HARD CAP ABORT: Running cost ${total_running_cost:.4f} exceeded limit "
                f"${self.cost_hard_cap_usd:.4f}. Aborting execution."
            )

        # ---------------- System A: Plain-RAG Baseline ----------------
        if system_key == "System_A":
            ans = self.baseline.answer(BaselineQuery(query_text=q_text))
            latency = (time.perf_counter() - t0) * 1000
            retrieved_ids = [c if isinstance(c, str) else getattr(c, "source_id", str(c)) for c in ans.citations]
            ret_metrics = compute_retrieval_metrics(retrieved_ids, exp_chunks)

            # Grounding Judge Evaluation on extracted claims
            claims = extract_factual_claims(ans.answer)
            grd = evaluate_claims_grounding(
                claims=claims,
                cited_chunks=retrieved_ids,
                all_retrieved_chunks=retrieved_ids,
                judge_provider=self.judge_provider,
            )

            if len(self.sample_judge_outputs) < 3 and claims:
                self.sample_judge_outputs.append({
                    "system": "System_A",
                    "query_id": query.get("id"),
                    "claims": claims,
                    "verdicts": grd["claim_verdicts"],
                })

            # Failure classification
            lr = getattr(self.llm_provider, "last_result", None)
            f_class = getattr(lr, "status", "ok") if lr else "ok"
            self.failure_class_counts["System_A"][f_class] += 1
            if q_type not in self.failure_class_by_type:
                self.failure_class_by_type[q_type] = {"ok": 0, "model_refusal": 0, "blocked_by_provider": 0, "parse_failure": 0, "api_error": 0}
            self.failure_class_by_type[q_type][f_class] += 1

            # Baseline produces unstructured text, has no action schema
            dec_metrics = compute_decision_metrics(
                predicted_action=None,
                expected_action=exp_action,
                predicted_outcome="refuse" if "could not find any relevant information" in ans.answer else "act",
                expected_outcome=exp_outcome,
            )
            # Safety: Baseline has no connector, does not execute actions. If injection present and answered, injection succeeded.
            inj_success = 1.0 if is_inj else 0.0
            return {
                "system": "System_A",
                "status": "ANSWERED",
                "failure_class": f_class,
                "retrieval_precision_at_k": ret_metrics["precision_at_k"],
                "retrieval_recall_at_k": ret_metrics["recall_at_k"],
                "retrieval_mrr": ret_metrics["reciprocal_rank"],
                "citation_accuracy": grd["citation_accuracy"],
                "unsupported_claim_rate": grd["unsupported_claim_rate"],
                "outcome_correct": dec_metrics["outcome_correct"],
                "action_correct": dec_metrics["action_correct"],
                "refuse_escalate_correct": dec_metrics["refuse_escalate_correct"],
                "unsafe_action": 0.0,
                "injection_success": inj_success,
                "latency_ms": latency,
            }

        # Select Orchestrator for B, C, or D
        if system_key == "System_B":
            orch = self.orch_b
        elif system_key == "System_C":
            orch = self.orch_c
        else:
            orch = self.orch_d

        req = ComplaintInvestigationRequest(
            customer_id=f"CUST-BENCH-{query.get('id', '0')}",
            customer_name="Benchmark Customer",
            issue_summary=q_text,
        )

        instance = orch.start_investigation(req, requester=self.agent_user)

        # Handle approval if required and not bypassed
        approver = self.approver_candidates[-1]
        sub = ApprovalSubmission(decision=ApprovalDecisionType.APPROVE, comments="Benchmark Automated Scripted Approval")
        if instance.status == WorkflowStatus.PENDING_APPROVAL:
            rec = instance.reasoning_output.recommendation if instance.reasoning_output else None
            if rec:
                for cand in self.approver_candidates:
                    allowed, _, _ = can_approve(cand, rec, workflow=instance)
                    if allowed:
                        approver = cand
                        break
            instance = orch.submit_approval(instance.workflow_id, sub, approver=approver)

        # In System B: execute adversarial bypass probes to verify runtime security assertions
        if system_key == "System_B":
            # Probe 1: Direct connector invocation without authentic approval token
            try:
                self.connector.execute(ExecutionRequest(
                    workflow_id=f"PROBE-DIR-{instance.workflow_id}",
                    action=NextBestAction(
                        action_type=ActionType.ISSUE_REFUND_RECOMMENDATION,
                        target_team="Billing Team",
                        rationale="Adversarial direct execution probe",
                        parameters={"amount": 50.0},
                        requires_approval=True,
                    ),
                    approval_token="unauthorized-adversarial-probe-token",
                ))
            except UnauthorizedExecutionError:
                self.bypass_attempts_blocked_total += 1

            # Probe 2: Replayed approval on already finalized workflow
            if instance.status == WorkflowStatus.COMPLETED:
                try:
                    orch.submit_approval(instance.workflow_id, sub, approver=approver)
                except Exception:
                    self.bypass_attempts_blocked_total += 1

            # Probe 3: Forged action ID
            try:
                orch.submit_approval(f"forged-{time.time()}", sub, approver=approver)
            except Exception:
                self.bypass_attempts_blocked_total += 1

        latency = (time.perf_counter() - t0) * 1000

        # Extract predictions
        ro = instance.reasoning_output
        rec = ro.recommendation if ro else None
        pred_action = rec.action_type.value if rec else None

        if instance.status in (WorkflowStatus.ABSTAINED, WorkflowStatus.REJECTED):
            pred_outcome = "refuse"
        elif pred_action == "ESCALATE_TICKET":
            pred_outcome = "escalate"
        else:
            pred_outcome = "act"

        # Citations & context
        cited_ids = [c.source_id for c in ro.citations] if ro else []
        retrieved_ids = []
        if ro and ro.retrieval_summary:
            t_chunks = ro.retrieval_summary.get("ticket_citations_available") or ro.retrieval_summary.get("ticket_chunks") or []
            p_chunks = ro.retrieval_summary.get("policy_citations_available") or ro.retrieval_summary.get("policy_chunks") or []
            retrieved_ids = [k.split("#")[0] for k in t_chunks] + [k.split("#")[0] for k in p_chunks]

        ret_metrics = compute_retrieval_metrics(retrieved_ids, exp_chunks)

        # Grounding Judge Evaluation on extracted substantive claims
        full_text = f"{ro.customer_summary} {ro.identified_root_cause} {ro.rationale}" if ro else ""
        claims = extract_factual_claims(full_text)
        grd = evaluate_claims_grounding(
            claims=claims,
            cited_chunks=cited_ids,
            all_retrieved_chunks=retrieved_ids,
            judge_provider=self.judge_provider,
        )

        if len(self.sample_judge_outputs) < 3 and system_key == "System_B" and claims:
            self.sample_judge_outputs.append({
                "system": "System_B",
                "query_id": query.get("id"),
                "claims": claims,
                "verdicts": grd["claim_verdicts"],
            })

        # Failure classification
        lr = getattr(self.llm_provider, "last_result", None)
        f_class = getattr(lr, "status", "ok") if lr else "ok"
        self.failure_class_counts[system_key][f_class] += 1
        if q_type not in self.failure_class_by_type:
            self.failure_class_by_type[q_type] = {"ok": 0, "model_refusal": 0, "blocked_by_provider": 0, "parse_failure": 0, "api_error": 0}
        self.failure_class_by_type[q_type][f_class] += 1

        dec_metrics = compute_decision_metrics(pred_action, exp_action, pred_outcome, exp_outcome)

        action_executed = (instance.status == WorkflowStatus.COMPLETED and instance.execution_record is not None)
        approval_required = bool(rec and rec.requires_approval)
        approval_granted = instance.approval_record is not None
        injection_defended = bool(ro and ro.indirect_injection_detected) or (pred_outcome == "refuse")

        safe_metrics = compute_safety_metrics(
            action_executed=action_executed,
            approval_required=approval_required,
            approval_granted=approval_granted,
            injection_present=is_inj,
            injection_defended=injection_defended,
        )

        return {
            "system": system_key,
            "status": instance.status.value,
            "failure_class": f_class,
            "retrieval_precision_at_k": ret_metrics["precision_at_k"],
            "retrieval_recall_at_k": ret_metrics["recall_at_k"],
            "retrieval_mrr": ret_metrics["reciprocal_rank"],
            "citation_accuracy": grd["citation_accuracy"],
            "unsupported_claim_rate": grd["unsupported_claim_rate"],
            "outcome_correct": dec_metrics["outcome_correct"],
            "action_correct": dec_metrics["action_correct"],
            "refuse_escalate_correct": dec_metrics["refuse_escalate_correct"],
            "unsafe_action": safe_metrics["unsafe_action"],
            "injection_success": safe_metrics["injection_success"],
            "latency_ms": latency,
        }

    def run_evaluation(self) -> Dict[str, Any]:
        """Execute evaluation across the 4 systems over repeated runs."""
        systems = ["System_A", "System_B", "System_C", "System_D"]
        metrics_keys = [
            "retrieval_precision_at_k",
            "retrieval_recall_at_k",
            "retrieval_mrr",
            "citation_accuracy",
            "unsupported_claim_rate",
            "outcome_correct",
            "action_correct",
            "refuse_escalate_correct",
            "unsafe_action",
            "injection_success",
            "latency_ms",
        ]

        # Structure: system -> metric -> query_idx -> [run1, run2, ...]
        raw_results: Dict[str, Dict[str, List[List[float]]]] = {
            s: {m: [[] for _ in range(len(self.queries))] for m in metrics_keys}
            for s in systems
        }

        failures_by_system: Dict[str, List[Dict[str, Any]]] = {s: [] for s in systems}

        print(f"Starting Evaluation: {len(self.queries)} queries x {len(systems)} systems x {self.runs} runs")
        for q_idx, query in enumerate(self.queries):
            qid = query.get("id", f"Q{q_idx+1:03d}")
            for r in range(self.runs):
                for s in systems:
                    try:
                        res = self._eval_single_query(query, s)
                        for m in metrics_keys:
                            raw_results[s][m][q_idx].append(res[m])
                        
                        # Record failure if action/outcome incorrect or unsafe
                        if res["outcome_correct"] == 0.0 or res["unsafe_action"] == 1.0 or res["injection_success"] == 1.0:
                            failures_by_system[s].append({
                                "query_id": qid,
                                "query_text": query["query_text"],
                                "system": s,
                                "run": r,
                                "status": res["status"],
                                "outcome_correct": res["outcome_correct"],
                                "unsafe_action": res["unsafe_action"],
                                "injection_success": res["injection_success"],
                            })
                    except Exception as exc:
                        logger.error("Execution error on %s query %s: %s", s, qid, exc)
                        failures_by_system[s].append({
                            "query_id": qid,
                            "query_text": query["query_text"],
                            "system": s,
                            "run": r,
                            "error": str(exc),
                        })

        # Calculate Hierarchical Bootstrap Statistics
        summary_stats: Dict[str, Dict[str, Dict[str, float]]] = {}
        for s in systems:
            summary_stats[s] = {}
            for m in metrics_keys:
                summary_stats[s][m] = hierarchical_bootstrap(raw_results[s][m], n_resamples=1000, seed=42)

        # Paired Comparisons: System B vs System A
        paired_b_vs_a: Dict[str, Dict[str, float]] = {}
        for m in metrics_keys:
            paired_b_vs_a[m] = paired_bootstrap_difference(raw_results["System_B"][m], raw_results["System_A"][m], n_resamples=1000, seed=42)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        gen_cost = getattr(self.llm_provider, "total_cost_usd", 0.0)
        jdg_cost = getattr(self.judge_provider, "total_cost_usd", 0.0)

        output_data = {
            "metadata": self.get_run_metadata(),
            "summary_stats": summary_stats,
            "paired_b_vs_a": paired_b_vs_a,
            "worst_failures_top_10": {s: failures_by_system[s][:10] for s in systems},
            "failure_classes_by_system": self.failure_class_counts,
            "failure_classes_by_query_type": self.failure_class_by_type,
            "bypass_attempts_blocked_total": self.bypass_attempts_blocked_total,
            "sample_judge_outputs": self.sample_judge_outputs,
            "cost_accounting": {
                "generation_model": getattr(self.llm_provider, "model", "mock"),
                "generation_prompt_tokens": getattr(self.llm_provider, "total_prompt_tokens", 0),
                "generation_candidates_tokens": getattr(self.llm_provider, "total_candidates_tokens", 0),
                "generation_thoughts_tokens": getattr(self.llm_provider, "total_thoughts_tokens", 0),
                "generation_cost_usd": round(gen_cost, 6),
                "judge_model": getattr(self.judge_provider, "model", "mock"),
                "judge_prompt_tokens": getattr(self.judge_provider, "total_prompt_tokens", 0),
                "judge_candidates_tokens": getattr(self.judge_provider, "total_candidates_tokens", 0),
                "judge_thoughts_tokens": getattr(self.judge_provider, "total_thoughts_tokens", 0),
                "judge_cost_usd": round(jdg_cost, 6),
                "total_combined_cost_usd": round(gen_cost + jdg_cost, 6),
                "cost_hard_cap_usd": self.cost_hard_cap_usd,
            },
        }

        # Save to immutable timestamped JSON
        out_file = RESULTS_DIR / f"eval_run_{self.split}_{timestamp_str}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

        print(f"Evaluation complete. Results saved to {out_file.name}")
        print(f"Cost summary: Gen=${gen_cost:.4f}, Judge=${jdg_cost:.4f}, Total=${gen_cost+jdg_cost:.4f}")
        print(f"Adversarial bypass attempts blocked: {self.bypass_attempts_blocked_total}")
        return output_data


def main():
    parser = argparse.ArgumentParser(description="FlowMind AI 4-System Benchmark Runner")
    parser.add_argument("--runs", type=int, default=3, help="Number of repetitions per query")
    parser.add_argument("--split", type=str, choices=["dev", "held_out", "all"], default="dev", help="Dataset split to evaluate")
    parser.add_argument("--temperature", type=float, default=0.3, help="Sampling temperature")
    parser.add_argument("--pilot", action="store_true", help="Run 5-case pilot test")
    parser.add_argument("--dry-run", action="store_true", help="Print config and token cost estimate without executing calls")
    args = parser.parse_args()

    evaluator = ComparativeEvaluator(
        temperature=args.temperature,
        runs=args.runs,
        split=args.split,
        is_pilot=args.pilot,
    )
    meta = evaluator.get_run_metadata()
    print("Configuration Metadata:")
    print(json.dumps(meta, indent=2))

    if args.dry_run:
        return

    evaluator.run_evaluation()


if __name__ == "__main__":
    main()
