"""
Run 20 JSON-constrained test calls on candidate models (generator and judge)
and measure parse-failure rate and schema_deviation rate.
"""
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.reasoning.llm_provider import OllamaLLMProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeneratorOutputSchema(BaseModel):
    status: str = Field(description="Workflow status")
    customer_summary: str = Field(min_length=5)
    confidence_score: float = Field(ge=0.0, le=1.0)
    requires_human_approval: bool


class JudgeOutputSchema(BaseModel):
    is_supported: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=5)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            if val > 1.0 and val <= 100.0:
                return val / 100.0
            return val
        except Exception:
            return 0.0


def test_generator_json_reliability(n_calls: int = 20):
    print(f"\n========================================================")
    print(f"TESTING GENERATOR JSON RELIABILITY: llama3.1:8b ({n_calls} calls)")
    print(f"========================================================")
    provider = OllamaLLMProvider(model="llama3.1:8b", temperature=0.3, num_ctx=8192)

    parse_failures = 0
    schema_deviations = 0

    test_prompts = [
        f"Complaint #{i}: Customer reports delayed delivery and asks for fee waiver of ${10 + i}. Assess situation and return structured JSON."
        for i in range(1, n_calls + 1)
    ]

    for idx, prompt in enumerate(test_prompts):
        res = provider.generate_detailed(
            prompt=prompt,
            system_prompt="You are an enterprise AI. Respond strictly conforming to the requested JSON schema.",
            temperature=0.3,
            response_schema=GeneratorOutputSchema,
            json_mode=True,
        )
        if res.status == "parse_failure":
            parse_failures += 1
            if "Schema validation" in (res.error_message or ""):
                schema_deviations += 1
            print(f"[{idx+1}/{n_calls}] FAILED: {res.error_message}")
        else:
            print(f"[{idx+1}/{n_calls}] SUCCESS ({res.latency_ms:.0f}ms)")

    provider.unload()

    pf_rate = (parse_failures / n_calls) * 100.0
    sd_rate = (schema_deviations / n_calls) * 100.0

    print(f"\n--- Generator JSON Reliability Results ---")
    print(f"Total Calls:        {n_calls}")
    print(f"Parse Failures:     {parse_failures} ({pf_rate:.1f}%)")
    print(f"Schema Deviations:  {schema_deviations} ({sd_rate:.1f}%)")

    return {"model": "llama3.1:8b", "calls": n_calls, "parse_failure_rate": pf_rate, "schema_deviation_rate": sd_rate}


def test_judge_json_reliability(n_calls: int = 20):
    print(f"\n========================================================")
    print(f"TESTING JUDGE JSON RELIABILITY: qwen2.5:7b ({n_calls} calls)")
    print(f"========================================================")
    provider = OllamaLLMProvider(model="qwen2.5:7b", temperature=0.0, num_ctx=8192)

    parse_failures = 0
    schema_deviations = 0

    test_prompts = [
        f"Claim #{i}: Policy allows refund within {14 + (i%5)} days. Evidence: Standard cooling-off period is 14 days."
        for i in range(1, n_calls + 1)
    ]

    for idx, prompt in enumerate(test_prompts):
        res = provider.generate_detailed(
            prompt=prompt,
            system_prompt="You are an academic judge. Evaluate whether the evidence supports the claim. Return strictly conforming JSON.",
            temperature=0.0,
            response_schema=JudgeOutputSchema,
            json_mode=True,
        )
        if res.status == "parse_failure":
            parse_failures += 1
            if "Schema validation" in (res.error_message or ""):
                schema_deviations += 1
            print(f"[{idx+1}/{n_calls}] FAILED: {res.error_message}")
        else:
            print(f"[{idx+1}/{n_calls}] SUCCESS ({res.latency_ms:.0f}ms)")

    provider.unload()

    pf_rate = (parse_failures / n_calls) * 100.0
    sd_rate = (schema_deviations / n_calls) * 100.0

    print(f"\n--- Judge JSON Reliability Results ---")
    print(f"Total Calls:        {n_calls}")
    print(f"Parse Failures:     {parse_failures} ({pf_rate:.1f}%)")
    print(f"Schema Deviations:  {schema_deviations} ({sd_rate:.1f}%)")

    return {"model": "qwen2.5:7b", "calls": n_calls, "parse_failure_rate": pf_rate, "schema_deviation_rate": sd_rate}


if __name__ == "__main__":
    test_generator_json_reliability(20)
    test_judge_json_reliability(20)
