"""
Unit tests for deterministic judge pre-check entity normalization and grounding guards (Phase 4).
Tests:
- $49 vs $49.00 normalization
- 1,200 vs 1200 comma normalization
- Date format normalization (ISO 2026-10-21 vs October 21, 2026 vs 10/21/2026)
- Invariant: Pre-check may ONLY mark a claim UNSUPPORTED when an entity is missing.
  It must NEVER mark one SUPPORTED. Returns None when entities match, sending to LLM judge.
"""
import pytest
from backend.evaluation.judge_prompts import (
    check_deterministic_entailment,
    extract_normalized_numeric_values,
    extract_normalized_dates,
)


class TestJudgeDeterministicPreCheck:

    def test_numeric_currency_dollar_cents_normalization(self):
        # Claim uses $49.00, evidence uses $49
        claim = "The customer was charged a duplicate subscription fee of $49.00."
        evidence = ["Customer was billed $49 on their monthly invoice."]
        result = check_deterministic_entailment(claim, evidence)
        # MUST return None (delegate to LLM judge), NEVER is_supported=True!
        assert result is None

    def test_numeric_currency_missing_amount_unsupported(self):
        # Claim specifies $99.00, evidence only contains $49.00
        claim = "The customer was charged $99.00 for the renewal."
        evidence = ["Customer was billed $49 on their monthly invoice."]
        result = check_deterministic_entailment(claim, evidence)
        assert result is not None
        assert result["is_supported"] is False
        assert "99.0" in result["rationale"]

    def test_comma_formatted_numbers_normalization(self):
        # Claim uses $1,200, evidence uses 1200
        claim = "Customer requested compensation of $1,200 for hardware failure."
        evidence = ["The hardware replacement cost is 1200 dollars."]
        result = check_deterministic_entailment(claim, evidence)
        assert result is None

    def test_date_format_normalization_iso_vs_textual(self):
        # Claim uses 'October 21, 2026', evidence uses '2026-10-21'
        claim = "The complaint was filed on October 21, 2026."
        evidence = ["Incident record created on 2026-10-21 by customer Elena."]
        result = check_deterministic_entailment(claim, evidence)
        assert result is None

    def test_date_format_missing_date_unsupported(self):
        claim = "The outage occurred on 2026-11-15."
        evidence = ["Incident record created on 2026-10-21 by customer Elena."]
        result = check_deterministic_entailment(claim, evidence)
        assert result is not None
        assert result["is_supported"] is False
        assert "2026-11-15" in result["rationale"]

    def test_precheck_never_returns_true(self):
        # When all entities match, pre-check MUST return None, NEVER True
        claims = [
            "",
            "   ",
            "The customer was billed $49.",
            "Policy requires manager sign-off.",
        ]
        evidence = ["Customer was billed $49. Policy requires manager sign-off."]
        for c in claims:
            res = check_deterministic_entailment(c, evidence)
            if res is not None:
                assert res["is_supported"] is False, f"Pre-check returned {res} for claim '{c}', violating NEVER TRUE invariant!"

    def test_empty_evidence_marked_unsupported(self):
        claim = "The customer was charged $49."
        result = check_deterministic_entailment(claim, [])
        assert result is not None
        assert result["is_supported"] is False
