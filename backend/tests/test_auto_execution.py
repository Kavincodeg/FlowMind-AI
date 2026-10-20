"""
FlowMind AI - Auto-Execution Policy Tests (Prompt 3 Task 4 & Task 8)
Tests the 5 conditions from Customer Query Handling Policy for FlowMind acting alone:
1. Standard resolution with no money, no escalation, no team transfer.
2. Priority is 'low' or 'medium'.
3. No flags: legal, security, repeat_contact, sla_breach, fraud, injection, or financial amount.
4. Category is not 'billing', and 'security' not in flags.
5. At least 2 distinct cited sources and confidence >= 0.80.

Verifies:
- All 5 conditions passing returns True
- Each condition failing ALONE sends the case to approval (returns False)
- Missing / unknown priority, category, or flags sends to approval (returns False)
"""
from decimal import Decimal
import pytest

from backend.reasoning.auto_execution import check_auto_execution, is_auto_executable
from backend.reasoning.models import (
    ActionType,
    ComplaintInvestigationRequest,
    EscalationLevel,
    EvidenceCitation,
    NextBestAction,
    ReasoningOutput,
)


def make_valid_setup():
    """Create a baseline setup where all 5 conditions PASS."""
    citations = [
        EvidenceCitation(
            source_type="policy",
            source_id="customer_query_handling_policy.md",
            chunk_index=0,
            snippet="Standard resolutions may proceed automatically.",
        ),
        EvidenceCitation(
            source_type="ticket",
            source_id="TKT-1020",
            chunk_index=0,
            snippet="Delivery status normal.",
        ),
    ]

    action = NextBestAction(
        action_type=ActionType.RESOLVE_STANDARD,
        target_team="Customer Support",
        escalation_level=None,
        amount=None,
        is_cross_team=False,
    )

    reasoning = ReasoningOutput(
        status="RECOMMENDATION_READY",
        customer_summary="Package tracking request.",
        identified_root_cause="Normal transit timeline.",
        recommendation=action,
        rationale="Standard query within normal resolution window.",
        citations=citations,
        confidence_score=0.92,
        requires_human_approval=False,
        indirect_injection_detected=False,
    )

    request = ComplaintInvestigationRequest(
        customer_id="CUST-1020",
        customer_name="Sarah Connor",
        issue_summary="Where is my standard shipment package tracking?",
        priority="low",
        category="delivery",
        flags=[],
    )

    return reasoning, request


class TestAutoExecutionPolicy:
    """Test suite for 5-condition auto-execution policy."""

    def test_all_five_conditions_passing_auto_executes(self):
        """Baseline happy path: all conditions met -> auto-executable."""
        reasoning, request = make_valid_setup()
        res = check_auto_execution(reasoning, request)
        assert res["all_passed"] is True
        assert res["condition_1_standard_action"] is True
        assert res["condition_2_priority_low_or_medium"] is True
        assert res["condition_3_no_prohibited_flags"] is True
        assert res["condition_4_non_billing_and_non_security"] is True
        assert res["condition_5_citations_and_confidence"] is True
        assert len(res["reasons"]) == 0
        assert is_auto_executable(reasoning, request) is True

    # ------------------------------------------------------------------
    # Condition 1: Standard resolution, no money, no escalation, no transfer
    # ------------------------------------------------------------------
    def test_condition_1_fails_on_escalation_action(self):
        """Action type ESCALATE_TICKET fails Condition 1 alone."""
        reasoning, request = make_valid_setup()
        assert reasoning.recommendation is not None
        reasoning.recommendation.action_type = ActionType.ESCALATE_TICKET
        res = check_auto_execution(reasoning, request)
        assert res["condition_1_standard_action"] is False
        assert res["condition_2_priority_low_or_medium"] is True
        assert res["condition_4_non_billing_and_non_security"] is True
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_1_fails_on_escalation_level(self):
        """Having an escalation level (e.g. L1) fails Condition 1 alone."""
        reasoning, request = make_valid_setup()
        assert reasoning.recommendation is not None
        reasoning.recommendation.escalation_level = EscalationLevel.L1
        res = check_auto_execution(reasoning, request)
        assert res["condition_1_standard_action"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_1_fails_on_refund_amount(self):
        """Recommendation carrying an amount fails Condition 1."""
        reasoning, request = make_valid_setup()
        assert reasoning.recommendation is not None
        reasoning.recommendation.amount = Decimal("25.00")
        res = check_auto_execution(reasoning, request)
        assert res["condition_1_standard_action"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_1_fails_on_team_transfer(self):
        """Action type TRANSFER_TEAM fails Condition 1."""
        reasoning, request = make_valid_setup()
        assert reasoning.recommendation is not None
        reasoning.recommendation.action_type = ActionType.TRANSFER_TEAM
        res = check_auto_execution(reasoning, request)
        assert res["condition_1_standard_action"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    # ------------------------------------------------------------------
    # Condition 2: Priority is low or medium
    # ------------------------------------------------------------------
    @pytest.mark.parametrize("priority", ["high", "critical", "urgent", ""])
    def test_condition_2_fails_on_high_or_unknown_priority(self, priority):
        """Priority other than low or medium fails Condition 2 alone."""
        reasoning, request = make_valid_setup()
        request.priority = priority
        res = check_auto_execution(reasoning, request)
        assert res["condition_2_priority_low_or_medium"] is False
        assert res["condition_1_standard_action"] is True
        assert res["condition_3_no_prohibited_flags"] is True
        assert res["condition_4_non_billing_and_non_security"] is True
        assert res["condition_5_citations_and_confidence"] is True
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_2_fails_on_missing_priority(self):
        """Missing priority (None) fails Condition 2 alone."""
        reasoning, request = make_valid_setup()
        request.priority = None
        res = check_auto_execution(reasoning, request)
        assert res["condition_2_priority_low_or_medium"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_2_passes_on_medium_priority(self):
        """Priority 'medium' passes Condition 2."""
        reasoning, request = make_valid_setup()
        request.priority = "medium"
        res = check_auto_execution(reasoning, request)
        assert res["condition_2_priority_low_or_medium"] is True
        assert res["all_passed"] is True
        assert is_auto_executable(reasoning, request) is True

    # ------------------------------------------------------------------
    # Condition 3: Prohibited flags, injection, financial amount
    # ------------------------------------------------------------------
    @pytest.mark.parametrize("flag", [
        "legal",
        "security",
        "repeat_contact",
        "sla_breach",
        "fraud",
        "injection",
    ])
    def test_condition_3_fails_on_prohibited_flag(self, flag):
        """Any prohibited flag fails Condition 3."""
        reasoning, request = make_valid_setup()
        request.flags = [flag]
        res = check_auto_execution(reasoning, request)
        assert res["condition_3_no_prohibited_flags"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_3_fails_on_missing_flags(self):
        """Flags field missing (None) fails Condition 3."""
        reasoning, request = make_valid_setup()
        request.flags = None
        res = check_auto_execution(reasoning, request)
        assert res["condition_3_no_prohibited_flags"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_3_fails_on_indirect_injection(self):
        """Indirect prompt injection detection fails Condition 3."""
        reasoning, request = make_valid_setup()
        reasoning.indirect_injection_detected = True
        res = check_auto_execution(reasoning, request)
        assert res["condition_3_no_prohibited_flags"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_3_fails_on_financial_amount_in_request(self):
        """Financial amount detected in issue_summary fails Condition 3."""
        reasoning, request = make_valid_setup()
        request.issue_summary = "Customer claims their $30 package is missing."
        res = check_auto_execution(reasoning, request)
        assert res["condition_3_no_prohibited_flags"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    # ------------------------------------------------------------------
    # Condition 4: Category not billing, and security not in flags
    # ------------------------------------------------------------------
    def test_condition_4_fails_on_billing_category(self):
        """Category 'billing' fails Condition 4 alone."""
        reasoning, request = make_valid_setup()
        request.category = "billing"
        res = check_auto_execution(reasoning, request)
        assert res["condition_4_non_billing_and_non_security"] is False
        assert res["condition_1_standard_action"] is True
        assert res["condition_2_priority_low_or_medium"] is True
        assert res["condition_3_no_prohibited_flags"] is True
        assert res["condition_5_citations_and_confidence"] is True
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_4_fails_on_security_category(self):
        """Category containing security fails Condition 4."""
        reasoning, request = make_valid_setup()
        request.category = "security_review"
        res = check_auto_execution(reasoning, request)
        assert res["condition_4_non_billing_and_non_security"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_4_fails_on_missing_category(self):
        """Missing category (None) fails Condition 4."""
        reasoning, request = make_valid_setup()
        request.category = None
        res = check_auto_execution(reasoning, request)
        assert res["condition_4_non_billing_and_non_security"] is False
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    # ------------------------------------------------------------------
    # Condition 5: At least 2 distinct citations and confidence >= 0.80
    # ------------------------------------------------------------------
    def test_condition_5_fails_on_single_source_citation(self):
        """Only 1 distinct cited source fails Condition 5 alone."""
        reasoning, request = make_valid_setup()
        reasoning.citations = [
            EvidenceCitation(
                source_type="policy",
                source_id="policy.md",
                chunk_index=0,
                snippet="Rule text",
            ),
            EvidenceCitation(
                source_type="policy",
                source_id="policy.md",
                chunk_index=1,
                snippet="Rule text chunk 2",
            ),
        ]
        res = check_auto_execution(reasoning, request)
        assert res["condition_5_citations_and_confidence"] is False
        assert res["condition_1_standard_action"] is True
        assert res["condition_2_priority_low_or_medium"] is True
        assert res["condition_3_no_prohibited_flags"] is True
        assert res["condition_4_non_billing_and_non_security"] is True
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_5_fails_on_low_confidence(self):
        """Confidence score below 0.80 (e.g. 0.79) fails Condition 5 alone."""
        reasoning, request = make_valid_setup()
        reasoning.confidence_score = 0.79
        res = check_auto_execution(reasoning, request)
        assert res["condition_5_citations_and_confidence"] is False
        assert res["condition_1_standard_action"] is True
        assert res["condition_2_priority_low_or_medium"] is True
        assert res["condition_3_no_prohibited_flags"] is True
        assert res["condition_4_non_billing_and_non_security"] is True
        assert res["all_passed"] is False
        assert is_auto_executable(reasoning, request) is False

    def test_condition_5_passes_at_boundary_0_80(self):
        """Confidence score exactly 0.80 passes Condition 5."""
        reasoning, request = make_valid_setup()
        reasoning.confidence_score = 0.80
        res = check_auto_execution(reasoning, request)
        assert res["condition_5_citations_and_confidence"] is True
        assert res["all_passed"] is True
        assert is_auto_executable(reasoning, request) is True
