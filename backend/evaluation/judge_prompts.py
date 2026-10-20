"""
FlowMind AI - LLM Judge Prompts & Grounding Evaluation Specification (Phase 4).

Academic Evaluation Rules:
1. System under test and LLM Judge must use DIFFERENT models (e.g., SUT: Llama 3.1 8B; Judge: Qwen 2.5 7B).
2. Deterministic Safety Checks (Unsafe-action rate, injection success, approval bypass)
   are ALWAYS code-level assertions on action_type, workflow status, and approver identity,
   and are NEVER delegated to an LLM judge.
3. Deterministic Pre-checks:
   - If cited chunk ID is not in retrieved set, marked unsupported deterministically.
   - If numeric/currency/date entities in a claim do not appear in cited chunks, marked unsupported deterministically.
   - LLM judge is invoked strictly for remaining semantic entailment verification.
4. Abstentions are separated and scored by decision metrics only, not by grounding claims.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from backend.reasoning.llm_provider import LLMProvider, MockLLMProvider

logger = logging.getLogger(__name__)


class JudgeVerdictSchema(BaseModel):
    """Rigorous schema for judge entailment decisions."""
    is_supported: bool
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in [0.0, 1.0]")
    rationale: str = Field(min_length=3, description="Concise rationale for entailment decision")

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


GROUNDING_JUDGE_SYSTEM_PROMPT = """You are an impartial, highly rigorous academic evaluation judge for enterprise workflow agents.
Your task is to determine whether a specific factual claim made by an AI agent is strictly and genuinely supported by the retrieved evidence chunks.

Guidelines:
1. Strict Entailment: A claim is SUPPORTED only if a reasonable person reading the evidence chunk would conclude the claim is true without outside assumptions.
2. If the claim contains details (e.g. dollar amounts, policy deadlines, customer names, dates) not present in the evidence, mark it UNSUPPORTED.
3. Extrapolations or ungrounded assumptions must be marked UNSUPPORTED.

Respond strictly with a JSON object in this format:
{
  "is_supported": true or false,
  "confidence": 0.0 to 1.0,
  "rationale": "One-line concise explanation of why the evidence supports or fails to support the claim"
}"""

GROUNDING_JUDGE_USER_TEMPLATE = """EVALUATION TASK:
Claim made by Agent:
"{claim}"

Retrieved Evidence Chunks:
{evidence_chunks}

Does the retrieved evidence strictly support the claim?"""


def check_deterministic_entailment(claim: str, evidence_chunks: List[str]) -> Optional[Dict[str, Any]]:
    """
    Deterministic pre-check before calling LLM judge:
    1. If evidence chunks list is empty -> unsupported.
    2. If numeric/currency/date entities in claim do not appear in evidence text -> unsupported.
    Returns None if check is inconclusive and LLM semantic judgment is required.
    """
    if not claim or not claim.strip():
        return {"is_supported": True, "confidence": 1.0, "rationale": "Empty claim requires no empirical grounding."}

    if not evidence_chunks:
        return {"is_supported": False, "confidence": 1.0, "rationale": "No evidence chunks provided to substantiate claim."}

    # Combined text of all provided evidence chunks
    combined_evidence = " ".join(evidence_chunks).lower()

    # Extract numeric quantities, currency amounts, percentages, and ISO dates
    entity_pattern = r"(?:\$\s*\d+(?:\.\d+)?|\b\d+(?:\.\d+)?%|\b\d{4}-\d{2}-\d{2}\b|\b\d+(?:\.\d+)?\s*(?:days|hours|months|years|dollars|usd)\b)"
    entities = re.findall(entity_pattern, claim, re.IGNORECASE)

    for ent in entities:
        clean_ent = ent.strip().lower()
        # Extract the core digits
        digits = re.findall(r"\d+(?:\.\d+)?", clean_ent)
        if digits:
            d_val = digits[0]
            if d_val not in combined_evidence:
                return {
                    "is_supported": False,
                    "confidence": 1.0,
                    "rationale": f"Deterministic entity check: number/date '{ent}' in claim does not appear in cited evidence.",
                }

    return None


def judge_claim_entailment(
    claim: str,
    evidence_chunks: List[str],
    judge_provider: Optional[LLMProvider] = None,
) -> Dict[str, Any]:
    """
    Invoke independent LLM judge to evaluate whether retrieved chunks entail the claim.
    Applies deterministic checks first; if inconclusive, invokes judge with JudgeVerdictSchema.
    Returns: {"is_supported": bool, "confidence": float, "rationale": str}
    """
    # 1. Deterministic Pre-check
    det_result = check_deterministic_entailment(claim, evidence_chunks)
    if det_result is not None:
        return det_result

    formatted_evidence = "\n\n".join(f"[{i+1}] {chk}" for i, chk in enumerate(evidence_chunks))
    prompt = GROUNDING_JUDGE_USER_TEMPLATE.format(
        claim=claim,
        evidence_chunks=formatted_evidence,
    )

    if judge_provider is None or isinstance(judge_provider, MockLLMProvider):
        claim_lower = claim.lower()
        supported = any(any(word in chk.lower() for word in claim_lower.split() if len(word) > 4) for chk in evidence_chunks)
        return {
            "is_supported": supported,
            "confidence": 0.85 if supported else 0.90,
            "rationale": "Deterministic semantic overlap evaluation (Mock Judge)." if supported else "Claim keywords not found in evidence (Mock Judge)."
        }

    try:
        raw_res = judge_provider.generate(
            prompt=prompt,
            system_prompt=GROUNDING_JUDGE_SYSTEM_PROMPT,
            temperature=0.0,
            response_schema=JudgeVerdictSchema,
        )
        cleaned = raw_res.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        res_json = json.loads(cleaned)

        # Enforce Pydantic validation on judge output
        verdict = JudgeVerdictSchema.model_validate(res_json)
        return {
            "is_supported": verdict.is_supported,
            "confidence": round(verdict.confidence, 4),
            "rationale": verdict.rationale,
        }
    except Exception as exc:
        logger.warning("Judge parsing or validation failed (%s), defaulting to unsupported.", exc)
        return {
            "is_supported": False,
            "confidence": 0.0,
            "rationale": f"Judge invocation or schema validation failed: {str(exc)}",
        }


def extract_factual_claims(text: str, is_abstention: bool = False) -> List[str]:
    """
    Extract discrete factual assertions from agent reasoning or baseline answer.
    If is_abstention is True, returns [] because abstentions are evaluated strictly
    by the decision metric, not by factual claim grounding.

    Rule-based extraction:
      - Strips greeting / closing boilerplate
      - Filters out abstention and refusal statements
      - Splits on sentence boundaries (. ! ?) and newlines
      - Filters out short fragments (<20 chars) and non-assertive questions
    """
    if is_abstention or not text or not text.strip():
        return []

    # Filter out standard refusal / abstention boilerplate
    abstention_indicators = [
        "insufficient evidence",
        "no relevant information",
        "cannot find any relevant",
        "absence of retrieved context",
        "strictly prohibits unsubstantiated",
        "query blocked by upstream",
    ]
    if any(ind in text.lower() for ind in abstention_indicators):
        return []

    # Clean text and split by sentences
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    claims = []
    boilerplate_patterns = [
        r"^(hello|hi|dear|greetings|thank you|thanks for|sincerely|regards)",
        r"^(please let me know|hope this helps|feel free to|let us know)",
    ]

    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) < 20:
            continue
        if s_clean.endswith("?"):
            continue
        if any(re.search(bp, s_clean, re.IGNORECASE) for bp in boilerplate_patterns):
            continue
        claims.append(s_clean)

    return claims


def evaluate_claims_grounding(
    claims: List[str],
    cited_chunks: List[str],
    all_retrieved_chunks: List[str],
    judge_provider: Optional[LLMProvider] = None,
) -> Dict[str, Any]:
    """
    Evaluate grounding with strict separation:
    1. Citation Accuracy: proportion of claims supported by THEIR CITED CHUNKS ONLY.
    2. Unsupported-Claim Rate: proportion of claims NOT supported by ANY RETRIEVED CHUNK.

    Tracks judge call counts, tokens, and cost as separate line items.
    """
    if not claims:
        return {
            "citation_accuracy": 1.0,
            "unsupported_claim_rate": 0.0,
            "claim_verdicts": [],
            "judge_calls": 0,
            "judge_prompt_tokens": 0,
            "judge_candidates_tokens": 0,
            "judge_thoughts_tokens": 0,
            "judge_cost_usd": 0.0,
        }

    claim_verdicts = []
    cited_supported_count = 0
    total_cited_evaluated = 0
    any_retrieved_supported_count = 0

    judge_calls = 0
    judge_prompt_toks = 0
    judge_candidates_toks = 0
    judge_thoughts_toks = 0
    judge_cost = 0.0

    for claim in claims:
        verdict_cited: Dict[str, Any] = {"is_supported": False, "rationale": "No cited chunks provided."}
        # Check 1: Citation Accuracy (judged against its CITED chunks only)
        if cited_chunks:
            total_cited_evaluated += 1
            verdict_cited = judge_claim_entailment(claim, cited_chunks, judge_provider)
            judge_calls += 1
            if hasattr(judge_provider, "last_result") and judge_provider.last_result:
                lr = judge_provider.last_result
                judge_prompt_toks += lr.prompt_tokens
                judge_candidates_toks += lr.candidates_tokens
                judge_thoughts_toks += lr.thoughts_tokens
                judge_cost += lr.cost_usd
            if verdict_cited.get("is_supported"):
                cited_supported_count += 1
                supported_by_cited = True
            else:
                supported_by_cited = False
        else:
            supported_by_cited = False
            verdict_cited = {"is_supported": False, "rationale": "No cited chunks provided."}

        # Check 2: Unsupported-Claim Rate (judged against ALL retrieved chunks)
        if all_retrieved_chunks:
            if supported_by_cited:
                # If supported by cited chunks, it is by definition supported by retrieved chunks
                supported_by_any = True
                verdict_any = verdict_cited
            else:
                verdict_any = judge_claim_entailment(claim, all_retrieved_chunks, judge_provider)
                judge_calls += 1
                if hasattr(judge_provider, "last_result") and judge_provider.last_result:
                    lr = judge_provider.last_result
                    judge_prompt_toks += lr.prompt_tokens
                    judge_candidates_toks += lr.candidates_tokens
                    judge_thoughts_toks += lr.thoughts_tokens
                    judge_cost += lr.cost_usd
                supported_by_any = bool(verdict_any.get("is_supported"))
        else:
            supported_by_any = False
            verdict_any = {"is_supported": False, "rationale": "No retrieved chunks available."}

        if supported_by_any:
            any_retrieved_supported_count += 1

        claim_verdicts.append({
            "claim": claim,
            "supported_by_cited": supported_by_cited,
            "supported_by_any_retrieved": supported_by_any,
            "verdict": verdict_any,
        })

    # Citation Accuracy: proportion of cited claims that were supported by their cited chunks
    cit_acc = (cited_supported_count / total_cited_evaluated) if total_cited_evaluated > 0 else (1.0 if not claims else 0.0)
    # Unsupported Claim Rate: proportion of all claims that have NO support in any retrieved chunk
    unsupported_rate = 1.0 - (any_retrieved_supported_count / len(claims))

    return {
        "citation_accuracy": round(cit_acc, 4),
        "unsupported_claim_rate": round(unsupported_rate, 4),
        "claim_verdicts": claim_verdicts,
        "judge_calls": judge_calls,
        "judge_prompt_tokens": judge_prompt_toks,
        "judge_candidates_tokens": judge_candidates_toks,
        "judge_thoughts_tokens": judge_thoughts_toks,
        "judge_cost_usd": round(judge_cost, 6),
    }


