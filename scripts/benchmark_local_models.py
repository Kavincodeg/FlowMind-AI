"""
Benchmark local LLM performance (tokens/sec, latency, GPU thermal stats)
on 5 real benchmark queries with full retrieved context.
"""
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.llm_provider import OllamaLLMProvider
from backend.reasoning.models import ComplaintInvestigationRequest
from backend.retrieval.mock_retriever import mock_retrieve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"


def get_gpu_thermal_stats():
    """Query nvidia-smi for temperature, clock speed, and power draw."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu,clocks.current.graphics,power.draw", "--format=csv,noheader,nounits"],
            encoding="utf-8"
        ).strip()
        temp, clock, power = [s.strip() for s in out.split(",")]
        return float(temp), float(clock), float(power)
    except Exception as e:
        logger.warning("Could not read GPU thermal stats: %s", e)
        return None, None, None


def benchmark_generator(model_name: str = "llama3.1:8b"):
    print(f"\n========================================================")
    print(f"BENCHMARKING GENERATOR: {model_name}")
    print(f"========================================================")

    provider = OllamaLLMProvider(model=model_name, temperature=0.3, num_ctx=8192)
    engine = ReasoningEngine(retriever_fn=mock_retrieve, llm_provider=provider, enable_grounding_verification=True)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)

    # 5 stratified queries
    selected = []
    for t in ["normal", "multi_hop", "missing_evidence", "conflicting_policy", "adversarial"]:
        matches = [q for q in queries if q.get("benchmark_type") == t and q.get("split") == "dev"]
        if matches:
            selected.append(matches[0])
    if len(selected) < 5:
        selected = queries[:5]

    results = []
    start_temp, _, _ = get_gpu_thermal_stats()
    print(f"Initial GPU Temp: {start_temp} C")

    for idx, q in enumerate(selected):
        qid = q.get("id", f"Q{idx+1}")
        q_type = q.get("benchmark_type")
        q_text = q["query_text"]

        t0 = time.perf_counter()
        req = ComplaintInvestigationRequest(
            customer_id=f"CUST-{qid}",
            customer_name="Benchmark Customer",
            issue_summary=q_text,
        )
        output = engine.investigate(req)
        wall_sec = time.perf_counter() - t0

        lr = provider.last_result
        p_toks = lr.prompt_tokens if lr else 0
        c_toks = lr.candidates_tokens if lr else 0
        tok_per_sec = (c_toks / (wall_sec)) if wall_sec > 0 and c_toks > 0 else 0.0

        temp, clock, power = get_gpu_thermal_stats()

        res_item = {
            "query_id": qid,
            "type": q_type,
            "status": output.status,
            "wall_sec": round(wall_sec, 2),
            "prompt_tokens": p_toks,
            "eval_tokens": c_toks,
            "tokens_per_sec": round(tok_per_sec, 2),
            "gpu_temp_c": temp,
            "gpu_clock_mhz": clock,
            "gpu_power_w": power,
        }
        results.append(res_item)
        print(f"[{idx+1}/5] {qid} ({q_type}): {wall_sec:.2f}s | P:{p_toks} E:{c_toks} | {tok_per_sec:.2f} t/s | GPU: {temp}C, {clock}MHz")

    # Unload generator model to clear VRAM
    provider.unload()

    avg_sec = sum(r["wall_sec"] for r in results) / len(results)
    avg_tps = sum(r["tokens_per_sec"] for r in results) / len(results)
    max_temp = max(r["gpu_temp_c"] for r in results if r["gpu_temp_c"] is not None)

    print(f"\n--- Generator Summary ({model_name}) ---")
    print(f"Average Seconds/Call: {avg_sec:.2f}s")
    print(f"Average Tokens/Sec:   {avg_tps:.2f} t/s")
    print(f"Peak GPU Temp:        {max_temp} C")

    return {
        "model": model_name,
        "avg_seconds_per_call": avg_sec,
        "avg_tokens_per_sec": avg_tps,
        "peak_gpu_temp_c": max_temp,
        "results": results,
    }


def benchmark_judge(model_name: str = "qwen2.5:7b"):
    print(f"\n========================================================")
    print(f"BENCHMARKING JUDGE: {model_name}")
    print(f"========================================================")

    from backend.evaluation.judge_prompts import judge_claim_entailment

    provider = OllamaLLMProvider(model=model_name, temperature=0.0, num_ctx=8192)

    sample_tasks = [
        {
            "claim": "Customer experienced unexpected billing charges for international roaming totaling $45.00.",
            "evidence": ["Policy DOC-001: International roaming charges are capped at $50 per cycle.", "Ticket TKT-001: Customer disputed $45 roaming fee applied in July."],
        },
        {
            "claim": "The account cancellation fee was waived because the cancellation occurred within 14 days.",
            "evidence": ["Policy DOC-002: Cooling-off cancellation period allows 100% fee waiver within 14 days of subscription."],
        },
        {
            "claim": "Agent issued an unauthorized refund of $500 without managerial approval.",
            "evidence": ["Policy DOC-003: Refunds over $100 require Level 2 managerial approval."],
        },
        {
            "claim": "Customer reported router hardware malfunction with flashing red power indicator.",
            "evidence": ["Ticket TKT-004: Hardware diagnostic report indicates router failure with persistent red LED."],
        },
        {
            "claim": "The customer was promised a replacement device delivered within 24 hours.",
            "evidence": ["Policy DOC-005: Standard device replacements are dispatched within 3-5 business days."],
        },
    ]

    results = []
    start_temp, _, _ = get_gpu_thermal_stats()
    print(f"Initial GPU Temp: {start_temp} C")

    for idx, task in enumerate(sample_tasks):
        t0 = time.perf_counter()
        verdict = judge_claim_entailment(task["claim"], task["evidence"], judge_provider=provider)
        wall_sec = time.perf_counter() - t0

        lr = provider.last_result
        p_toks = lr.prompt_tokens if lr else 0
        c_toks = lr.candidates_tokens if lr else 0
        tok_per_sec = (c_toks / (wall_sec)) if wall_sec > 0 and c_toks > 0 else 0.0

        temp, clock, power = get_gpu_thermal_stats()

        res_item = {
            "claim_idx": idx + 1,
            "is_supported": verdict["is_supported"],
            "confidence": verdict["confidence"],
            "wall_sec": round(wall_sec, 2),
            "prompt_tokens": p_toks,
            "eval_tokens": c_toks,
            "tokens_per_sec": round(tok_per_sec, 2),
            "gpu_temp_c": temp,
        }
        results.append(res_item)
        print(f"[{idx+1}/5] Verdict: {verdict['is_supported']} (conf: {verdict['confidence']}) in {wall_sec:.2f}s | P:{p_toks} E:{c_toks} | {tok_per_sec:.2f} t/s | GPU: {temp}C")

    # Unload judge model to clear VRAM
    provider.unload()

    avg_sec = sum(r["wall_sec"] for r in results) / len(results)
    avg_tps = sum(r["tokens_per_sec"] for r in results) / len(results)
    max_temp = max(r["gpu_temp_c"] for r in results if r["gpu_temp_c"] is not None)

    print(f"\n--- Judge Summary ({model_name}) ---")
    print(f"Average Seconds/Call: {avg_sec:.2f}s")
    print(f"Average Tokens/Sec:   {avg_tps:.2f} t/s")
    print(f"Peak GPU Temp:        {max_temp} C")

    return {
        "model": model_name,
        "avg_seconds_per_call": avg_sec,
        "avg_tokens_per_sec": avg_tps,
        "peak_gpu_temp_c": max_temp,
        "results": results,
    }


if __name__ == "__main__":
    benchmark_judge("qwen2.5:7b")
