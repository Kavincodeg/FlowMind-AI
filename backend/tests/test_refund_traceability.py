"""
FlowMind AI - Refund Amount Traceability Tests (Prompt 3 Task 5)
Verifies:
1. ISSUE_REFUND_RECOMMENDATION must carry a structured positive Decimal amount.
2. The amount must appear in the customer request or in a cited ticket.
3. If the amount cannot be traced (e.g. model invents an amount not in evidence),
   the engine returns ABSTAINED with AbstentionReason.AMOUNT_NOT_VERIFIED.
4. If the amount is missing or non-positive, returns ABSTAINED with AMOUNT_NOT_VERIFIED.
5. If the amount appears in customer request, recommendation succeeds.
6. If the amount appears in a cited ticket, recommendation succeeds.
"""
from decimal import Decimal
import json
from typing import Optional
import pytest

from backend.reasoning.engine import ReasoningEngine
from backend.reasoning.llm_provider import LLMProvider
from backend.reasoning.models import (
    AbstentionReason,
    ActionType,
    ComplaintInvestigationRequest,
    EvidenceCitation,
)
from backend.retrieval.mock_retriever import make_mock_chunk
from backend.retrieval.models import RetrievalQuery, RetrievalResult


class CustomMockLLM(LLMProvider):
    """Test LLM returning configurable refund recommendation payloads."""

    def __init__(self, amount: Optional[float] = None, action_type: str = "ISSUE_REFUND_RECOMMENDATION"):
        self.amount = amount
        self.action_type = action_type

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.0) -> str:
        rec = {
            "action_type": self.action_type,
            "target_team": "Finance Operations",
            "escalation_level": "L1",
            "urgency": "medium",
            "parameters": {"duplicate_tx": "TX-1001"},
            "requires_approval": True,
        }
        if self.amount is not None:
            rec["amount"] = self.amount
            rec["parameters"]["amount"] = self.amount

        return json.dumps({
            "status": "RECOMMENDATION_READY",
            "abstention_reason": None,
            "customer_summary": "Customer billing dispute for duplicate charges.",
            "identified_root_cause": "Verified duplicate subscription billing transaction.",
            "recommendation": rec,
            "rationale": "Per Refund Policy, verified duplicate payment is eligible for refund.",
            "citations": [
                {
                    "source_type": "policy",
                    "source_id": "refund_policy.md",
                    "chunk_index": 0,
                    "snippet": "Duplicate transactions shall be refunded upon verification.",
                },
                {
                    "source_type": "ticket",
                    "source_id": "TKT-REF-100",
                    "chunk_index": 0,
                    "snippet": "Ticket details for billing inquiry.",
                },
            ],
            "confidence_score": 0.90,
            "requires_human_approval": True,
            "indirect_injection_detected": False,
        })


def mock_retriever_with_ticket_amount(query: RetrievalQuery) -> RetrievalResult:
    """Retriever returning a ticket chunk containing an explicit $120.00 charge."""
    chunk = make_mock_chunk(
        source_type="ticket",
        source_id="TKT-REF-100",
        chunk_index=0,
        content="Invoice audit confirmed customer was erroneously charged $120.00 twice on March 15.",
    )
    return RetrievalResult(
        query_text=query.query_text,
        chunks=[chunk],
        total_found=1,
        filters_applied={},
        retrieval_time_ms=1.0,
    )


class TestRefundAmountTraceability:
    """Test suite ensuring refund amounts must be traceable and never hallucinated."""

    def test_hallucinated_invented_amount_triggers_abstention(self):
        """
        When the model invents an amount ($750.00) that does NOT appear in the
        customer request or any cited ticket, the engine must return ABSTAINED
        with AMOUNT_NOT_VERIFIED.
        """
        llm = CustomMockLLM(amount=750.0)  # $750 is nowhere in the evidence
        engine = ReasoningEngine(retriever_fn=mock_retriever_with_ticket_amount, llm_provider=llm)

        request = ComplaintInvestigationRequest(
            customer_id="CUST-1008",
            customer_name="Elena Rostova",
            issue_summary="Duplicate charge dispute on credit card statement.",
            top_k_tickets=3,
            top_k_policies=2,
        )

        output = engine.investigate(request)

        assert output.status == "ABSTAINED"
        assert output.abstention_reason == AbstentionReason.AMOUNT_NOT_VERIFIED
        assert output.recommendation is None
        assert "AMOUNT_NOT_VERIFIED" in output.rationale

    def test_missing_amount_triggers_abstention(self):
        """
        When a refund recommendation carries no amount (amount=None),
        the engine must return ABSTAINED with AMOUNT_NOT_VERIFIED.
        """
        llm = CustomMockLLM(amount=None)  # Missing amount
        engine = ReasoningEngine(retriever_fn=mock_retriever_with_ticket_amount, llm_provider=llm)

        request = ComplaintInvestigationRequest(
            customer_id="CUST-1008",
            customer_name="Elena Rostova",
            issue_summary="Duplicate charge dispute on credit card statement for $120.00.",
        )

        output = engine.investigate(request)

        assert output.status == "ABSTAINED"
        assert output.abstention_reason == AbstentionReason.AMOUNT_NOT_VERIFIED
        assert output.recommendation is None

    def test_amount_in_customer_request_is_verified(self):
        """
        When the refund amount ($49.00) appears in the customer request,
        the recommendation succeeds with structured Decimal amount.
        """
        llm = CustomMockLLM(amount=49.0)
        engine = ReasoningEngine(retriever_fn=mock_retriever_with_ticket_amount, llm_provider=llm)

        request = ComplaintInvestigationRequest(
            customer_id="CUST-1008",
            customer_name="Elena Rostova",
            issue_summary="Customer charged twice ($49.00 each) for monthly subscription renewal.",
        )

        output = engine.investigate(request)

        assert output.status == "RECOMMENDATION_READY"
        assert output.abstention_reason is None
        assert output.recommendation is not None
        assert output.recommendation.action_type == ActionType.ISSUE_REFUND_RECOMMENDATION
        assert output.recommendation.amount == Decimal("49.00")

    def test_amount_in_cited_ticket_is_verified(self):
        """
        When the refund amount ($120.00) appears in the cited ticket chunk
        (even if omitted from the customer query), the recommendation succeeds.
        """
        llm = CustomMockLLM(amount=120.0)
        engine = ReasoningEngine(retriever_fn=mock_retriever_with_ticket_amount, llm_provider=llm)

        request = ComplaintInvestigationRequest(
            customer_id="CUST-1008",
            customer_name="Elena Rostova",
            issue_summary="Disputing duplicate billing on invoice from March 15.",
        )

        output = engine.investigate(request)

        assert output.status == "RECOMMENDATION_READY"
        assert output.abstention_reason is None
        assert output.recommendation is not None
        assert output.recommendation.action_type == ActionType.ISSUE_REFUND_RECOMMENDATION
        assert output.recommendation.amount == Decimal("120.00")

    def test_non_positive_amount_triggers_abstention(self):
        """Non-positive amounts (e.g. <= 0) cannot be verified and trigger abstention."""
        llm = CustomMockLLM(amount=0.0)
        engine = ReasoningEngine(retriever_fn=mock_retriever_with_ticket_amount, llm_provider=llm)

        request = ComplaintInvestigationRequest(
            customer_id="CUST-1008",
            customer_name="Elena Rostova",
            issue_summary="Duplicate charge of $0.00 fee waiver missing.",
        )

        output = engine.investigate(request)

        assert output.status == "ABSTAINED"
        assert output.abstention_reason == AbstentionReason.AMOUNT_NOT_VERIFIED
