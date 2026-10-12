"""
FlowMind AI - Automatic Execution Policy Engine (Phase 4 / Prompt 3)
Enforces the 5 conditions from Customer Query Handling Policy for FlowMind acting alone.

5 Conditions:
1. The action is a standard resolution with no money, no escalation and no team transfer.
2. Priority is 'low' or 'medium'.
3. No flags: legal, security, repeat_contact, sla_breach, fraud, injection, or a financial amount.
4. The category is not 'billing', and 'security' is not in the flags.
5. At least 2 distinct cited sources and confidence of at least 0.80.

If any needed field is missing or unknown, the case is not auto-executable.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.reasoning.models import (
    ActionType,
    ComplaintInvestigationRequest,
    NextBestAction,
    ReasoningOutput,
)


PROHIBITED_FLAGS: Set[str] = {
    "legal",
    "security",
    "repeat_contact",
    "sla_breach",
    "fraud",
    "injection",
}


def detect_financial_amount(text: str) -> bool:
    """Detect whether a financial monetary amount appears in the text."""
    if not text:
        return False
    pattern = r"(\$\s*\d+|\b\d+(?:\.\d{1,2})?\s*(?:dollars?|usd|bucks|cents|euro|gbp)\b)"
    return bool(re.search(pattern, text, re.IGNORECASE))


def check_auto_execution(
    reasoning_output: Optional[ReasoningOutput],
    request: Optional[ComplaintInvestigationRequest],
) -> Dict[str, Any]:
    """
    Evaluate all 5 policy conditions individually.
    Returns dictionary detailing pass/fail for each condition.
    """
    if reasoning_output is None or request is None:
        return {
            "condition_1_standard_action": False,
            "condition_2_priority_low_or_medium": False,
            "condition_3_no_prohibited_flags": False,
            "condition_4_non_billing_and_non_security": False,
            "condition_5_citations_and_confidence": False,
            "all_passed": False,
            "reasons": ["Missing reasoning output or request payload"],
        }

    rec: Optional[NextBestAction] = reasoning_output.recommendation
    reasons: List[str] = []

    # ------------------------------------------------------------------
    # Condition 1: Standard resolution with no money, no escalation, no transfer
    # ------------------------------------------------------------------
    cond1 = True
    if not rec:
        cond1 = False
        reasons.append("Condition 1 failed: No recommendation produced.")
    else:
        if rec.action_type not in (
            ActionType.RESOLVE_STANDARD,
            ActionType.REQUEST_CUSTOMER_INFO,
            ActionType.NO_ACTION,
        ):
            cond1 = False
            reasons.append(f"Condition 1 failed: Action '{rec.action_type.value}' is not a standard resolution.")

        # Check money
        has_money = (
            (rec.amount is not None and rec.amount > Decimal("0"))
            or (rec.parameters.get("amount") is not None and float(rec.parameters.get("amount") or 0) > 0)
            or detect_financial_amount(request.issue_summary)
        )
        if has_money:
            cond1 = False
            reasons.append("Condition 1 failed: Monetary amount detected in action or request.")

        # Check escalation
        if rec.escalation_level is not None:
            cond1 = False
            reasons.append(f"Condition 1 failed: Escalation level '{rec.escalation_level.value}' present.")

        # Check team transfer
        if rec.action_type == ActionType.TRANSFER_TEAM or getattr(rec, "is_cross_team", False):
            cond1 = False
            reasons.append("Condition 1 failed: Team transfer action detected.")

    # ------------------------------------------------------------------
    # Condition 2: Priority is low or medium
    # ------------------------------------------------------------------
    cond2 = True
    if request.priority is None or not request.priority.strip():
        cond2 = False
        reasons.append("Condition 2 failed: Priority field is missing.")
    elif request.priority.strip().lower() not in ("low", "medium"):
        cond2 = False
        reasons.append(f"Condition 2 failed: Priority '{request.priority}' is not 'low' or 'medium'.")

    # ------------------------------------------------------------------
    # Condition 3: No flags (legal, security, repeat_contact, sla_breach, fraud, injection, financial)
    # ------------------------------------------------------------------
    cond3 = True
    if request.flags is None:
        cond3 = False
        reasons.append("Condition 3 failed: Flags field is missing.")
    else:
        cleaned_flags = {f.strip().lower() for f in request.flags}
        found_prohibited = cleaned_flags.intersection(PROHIBITED_FLAGS)
        if found_prohibited:
            cond3 = False
            reasons.append(f"Condition 3 failed: Prohibited flags present: {found_prohibited}")

        # Computed injection
        if reasoning_output.indirect_injection_detected:
            cond3 = False
            reasons.append("Condition 3 failed: Indirect prompt injection detected.")

        # Computed financial amount
        if detect_financial_amount(request.issue_summary) or (rec and rec.amount and rec.amount > 0):
            cond3 = False
            reasons.append("Condition 3 failed: Financial monetary amount detected.")

    # ------------------------------------------------------------------
    # Condition 4: Category is not billing, and security not in flags
    # ------------------------------------------------------------------
    cond4 = True
    if request.category is None or not request.category.strip():
        cond4 = False
        reasons.append("Condition 4 failed: Category field is missing.")
    elif request.category.strip().lower() == "billing":
        cond4 = False
        reasons.append("Condition 4 failed: Category is 'billing'.")
    elif "security" in request.category.strip().lower():
        cond4 = False
        reasons.append("Condition 4 failed: Category involves security.")

    if request.flags is not None:
        if any(f.strip().lower() == "security" for f in request.flags):
            cond4 = False
            reasons.append("Condition 4 failed: 'security' flag present.")

    # ------------------------------------------------------------------
    # Condition 5: At least 2 distinct cited sources and confidence >= 0.80
    # ------------------------------------------------------------------
    cond5 = True
    distinct_sources = {c.source_id for c in reasoning_output.citations if c.source_id}
    if len(distinct_sources) < 2:
        cond5 = False
        reasons.append(f"Condition 5 failed: Only {len(distinct_sources)} distinct cited source(s) (requires at least 2).")

    if reasoning_output.confidence_score < 0.80:
        cond5 = False
        reasons.append(f"Condition 5 failed: Confidence score {reasoning_output.confidence_score:.2f} is below 0.80.")

    all_passed = cond1 and cond2 and cond3 and cond4 and cond5

    return {
        "condition_1_standard_action": cond1,
        "condition_2_priority_low_or_medium": cond2,
        "condition_3_no_prohibited_flags": cond3,
        "condition_4_non_billing_and_non_security": cond4,
        "condition_5_citations_and_confidence": cond5,
        "all_passed": all_passed,
        "reasons": reasons,
    }


def is_auto_executable(
    reasoning_output: Optional[ReasoningOutput],
    request: Optional[ComplaintInvestigationRequest],
) -> bool:
    """
    Evaluates whether the 5 conditions from Customer Query Handling Policy are met.
    Returns True if FlowMind may automatically execute without human approval; False otherwise.
    """
    result = check_auto_execution(reasoning_output, request)
    return bool(result["all_passed"])
