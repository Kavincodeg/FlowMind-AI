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


def extract_normalized_numeric_values(text: str) -> set[float]:
    """
    Extract and normalize all numeric values from text (handling currencies, commas, decimals, percentages).
    E.g., '$49', '$49.00' -> 49.0; '1,200', '1200', '1200.00' -> 1200.0; '15%' -> 15.0.
    Strips out dates first so that e.g. '2026-11-15' is not fragmented into numbers [2026, 11, 15].
    """
    # Strip ISO, slash, and textual dates first
    clean_text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
    clean_text = re.sub(r"\b\d{1,2}/\d{1,2}/\d{4}\b", " ", clean_text)
    months_pat = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    clean_text = re.sub(rf"\b({months_pat})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", " ", clean_text, flags=re.IGNORECASE)
    values = set()
    matches = re.findall(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)%?", clean_text)
    for m in matches:
        clean = m.replace(",", "").replace("$", "").strip()
        try:
            val = float(clean)
            values.add(val)
        except ValueError:
            pass
    return values


def extract_normalized_dates(text: str) -> set[str]:
    """
    Extract and normalize dates into canonical 'YYYY-MM-DD' strings.
    Supports ISO (2026-10-21), slash (10/21/2026 or 2026/10/21), and textual ('October 21, 2026', '21 Oct 2026').
    """
    dates = set()
    # ISO dates: YYYY-MM-DD
    for m in re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text):
        dates.add(m)
    # Textual dates: Month DD, YYYY
    months_pattern = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    for m in re.finditer(rf"\b({months_pattern})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", text, re.IGNORECASE):
        mon_str, day_str, yr_str = m.group(1), m.group(2), m.group(3)
        try:
            from datetime import datetime
            parsed = datetime.strptime(f"{mon_str[:3]} {day_str} {yr_str}", "%b %d %Y")
            dates.add(parsed.strftime("%Y-%m-%d"))
        except Exception:
            pass
    # Slash dates: MM/DD/YYYY
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text):
        try:
            from datetime import datetime
            parsed = datetime.strptime(f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%m/%d/%Y")
            dates.add(parsed.strftime("%Y-%m-%d"))
        except Exception:
            pass
    return dates


def check_deterministic_entailment(claim: str, evidence_chunks: List[str]) -> Optional[Dict[str, Any]]:
    """
    Deterministic pre-check before calling LLM judge:
    1. If evidence chunks list is empty -> UNSUPPORTED.
    2. If numeric/currency/date entities in claim do not appear in evidence text -> UNSUPPORTED.
    CRITICAL RULE: Pre-check may ONLY mark a claim UNSUPPORTED when a normalized entity is absent.
    It must NEVER mark a claim SUPPORTED. Send everything else to the LLM judge (returns None).
    """
    if not claim or not claim.strip():
        # Never mark supported; pass to LLM judge / downstream handler
        return None

    if not evidence_chunks:
        return {"is_supported": False, "confidence": 1.0, "rationale": "No evidence chunks provided to substantiate claim."}

    # Combined text of all provided evidence chunks
    combined_evidence = " ".join(evidence_chunks)

    # 1. Normalize dates (ISO, slash, natural text)
    ev_dates = extract_normalized_dates(combined_evidence)
    claim_dates = extract_normalized_dates(claim)

    for dt in claim_dates:
        if dt not in ev_dates:
            return {
                "is_supported": False,
                "confidence": 1.0,
                "rationale": f"Deterministic entity check: normalized date '{dt}' in claim does not appear in cited evidence.",
            }

    # 2. Normalize numbers and currency ($49 vs $49.00, 1,200 vs 1200)
    ev_numbers = extract_normalized_numeric_values(combined_evidence)
    claim_numbers = extract_normalized_numeric_values(claim)

    for num in claim_numbers:
        if num not in ev_numbers:
            return {
                "is_supported": False,
                "confidence": 1.0,
                "rationale": f"Deterministic entity check: normalized numeric entity '{num}' in claim does not appear in cited evidence.",
            }

    # Inconclusive deterministically - strictly delegate semantic entailment verification to LLM judge
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


