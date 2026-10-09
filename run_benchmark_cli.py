"""
FlowMind AI - Benchmark CLI (Phase 4)
Runs the comparative evaluation benchmark across FlowMind AI and the Plain-RAG Baseline,
generates summary tables, and exports markdown/json reports.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.evaluation.harness import EvaluationHarness
from backend.evaluation.reporter import BenchmarkReporter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run FlowMind AI vs Plain-RAG Comparative Evaluation Benchmark"
    )
    parser.add_argument(
        "--retriever",
        type=str,
        choices=["pgvector", "mock"],
        default="pgvector",
        help="Retrieval engine to evaluate ('pgvector' [default, real semantic search] or 'mock' [offline keyword logic test])",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save benchmark_report.md and benchmark_report.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )
    args = parser.parse_args()

    print("================================================================================")
    print(" FlowMind AI — Phase 4 Comparative Evaluation Harness & Performance Benchmarking")
    print("================================================================================")
    print(f"Configured Retrieval Source: {args.retriever}")
    print("Executing 30-case dual pipeline benchmark (FlowMind AI vs. Plain-RAG Baseline)...")

    if args.retriever == "pgvector":
        from backend.retrieval.store import _get_dsn
        import psycopg2
        try:
            conn = psycopg2.connect(_get_dsn())
            conn.close()
        except Exception as exc:
            print(f"\n[ERROR] PostgreSQL / pgvector database is unreachable: {exc}", file=sys.stderr)
            print("Cannot evaluate real retrieval with --retriever pgvector when database is down.", file=sys.stderr)
            print("Please ensure the database container is running or run with --retriever mock.", file=sys.stderr)
            return 1

        from backend.retrieval.retriever import retrieve
        harness = EvaluationHarness(retriever_fn=retrieve, retrieval_source="pgvector")
    else:
        from backend.retrieval.mock_retriever import mock_retrieve
        harness = EvaluationHarness(retriever_fn=mock_retrieve, retrieval_source="mock")

    result = harness.run_comparative_benchmark()

    out_dir = Path(args.output_dir) if args.output_dir else None
    md_path, json_path = BenchmarkReporter.save_reports(result, out_dir)

    print(f"\n[Artifacts Written]")
    print(f" - Markdown Report: {md_path}")
    print(f" - JSON Report:     {json_path}")
    print(f" - LLM Provider:    {result.llm_provider}")
    print(f" - Retrieval Source:{result.retrieval_source}")

    cs = result.comparative_summary
    print("\n[Comparative Summary Table (30-Case Offline Logic Test)]")
    print(f" Total Benchmark Cases:                {cs.total_cases}")
    print(f" FlowMind Task Success Rate:           {cs.flowmind_task_success_rate:.1%}")
    print(f" Baseline Task Success Rate:           {cs.baseline_task_success_rate:.1%}")
    print(f" FlowMind Action Execution Accuracy:   {cs.flowmind_action_accuracy:.1%}")
    print(f" Baseline Action Execution Accuracy:   {cs.baseline_action_accuracy:.1%}")
    print(f" FlowMind Citation Integrity Rate:     {cs.flowmind_citation_integrity_rate:.1%}")
    print(f" FlowMind Approval Gating Compliance:  {cs.flowmind_approval_compliance_rate:.1%}")
    print(f" FlowMind Prompt Injection Defense:    {cs.flowmind_injection_defense_rate:.1%}")
    print(f" FlowMind Audit Completeness:          {cs.flowmind_audit_completeness_rate:.1%}")
    print(f" Baseline Audit Completeness:          {cs.baseline_audit_completeness_rate:.1%}")
    print(f" FlowMind Mean Latency:                {cs.flowmind_mean_latency_ms:.1f} ms")
    print(f" Baseline Mean Latency:                {cs.baseline_mean_latency_ms:.1f} ms")

    rm = result.retrieval_metrics
    if result.retrieval_source == "mock":
        print("\n[Mock keyword retriever (offline logic test)]")
    else:
        print("\n[Information Retrieval Quality (pgvector Semantic Vector Search)]")
    print(f" Retrieval Engine:                     {result.retrieval_source}")
    print(f" Precision@3:                          {rm.precision_at_3:.3f}")
    print(f" Precision@5:                          {rm.precision_at_5:.3f}")
    print(f" Recall@5:                             {rm.recall_at_5:.3f}")
    print(f" Mean Reciprocal Rank (MRR):           {rm.mrr:.3f}")
    print(f" Mean Retrieval Latency:               {rm.mean_latency_ms:.1f} ms")
    print(f" Total Evaluated Queries:              {rm.total_queries}")

    if args.json:
        print("\n[JSON Output]")
        print(result.model_dump_json(indent=2))

    print("\nBenchmark completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
