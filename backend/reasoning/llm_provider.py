"""
FlowMind AI - Replaceable LLM Provider Interface (Phase 2)
Provides an abstract LLM interface, a deterministic policy-grounded Mock provider,
and an Anthropic Claude provider.
"""
from __future__ import annotations

import abc
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMProvider(abc.ABC):
    """Abstract interface for LLM text generation."""

    @abc.abstractmethod
    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.0) -> str:
        """Generate response text for the given user prompt and system instructions."""
        pass


# ============================================================
# Mock LLM Provider (Offline, Deterministic, Policy-Aware)
# ============================================================

class MockLLMProvider(LLMProvider):
    """
    Deterministic mock provider implementing business logic for Customer Complaint Escalation.
    Operates offline without API keys, suitable for tests, evaluation benchmarks, and CI.
    """

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"override\s+(the\s+)?system",
        r"grant\s+\$?\d+[\d,]*\s*(refund|credit)\s+immediately",
        r"bypass\s+(the\s+)?(approval|routing)",
        r"you\s+are\s+now\s+in\s+developer\s+mode",
        r"do\s+not\s+follow\s+any\s+policy",
    ]

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.0) -> str:
        """Analyze prompt contents and synthesize an evidence-grounded response."""
        # Check if caller is requesting plain-RAG baseline answer
        if "customer support assistant" in system_prompt.lower() or "retrieved context:" in prompt.lower():
            return self._generate_baseline_plain_answer(prompt)

        # Extract the untrusted evidence and user request body to avoid matching template instructions
        evidence_block = ""
        evidence_match = re.search(r"<untrusted_retrieved_evidence>(.*?)</untrusted_retrieved_evidence>", prompt, re.DOTALL | re.IGNORECASE)
        if evidence_match:
            evidence_block = evidence_match.group(1).lower()

        request_match = re.search(r"INVESTIGATION REQUEST:\s*(.*?)(?=<untrusted_retrieved_evidence>|\Z)", prompt, re.DOTALL | re.IGNORECASE)
        issue_summary_lower = request_match.group(1).lower() if request_match else ""
        content_to_check = f"{issue_summary_lower}\n{evidence_block}"

        # 1. Detect indirect prompt injection
        injection_detected = any(
            re.search(pat, content_to_check, re.IGNORECASE) for pat in self.INJECTION_PATTERNS
        )

        # 2. Check for missing or insufficient evidence (abstention triggers)
        has_no_tickets = "[no relevant customer tickets retrieved]" in content_to_check
        has_no_policies = "[no relevant policy documents retrieved]" in content_to_check
        is_empty_or_vague = "issue summary: vague" in content_to_check or ("unknown customer" in content_to_check and has_no_tickets)

        if has_no_tickets and has_no_policies:
            return json.dumps({
                "status": "ABSTAINED",
                "abstention_reason": "INSUFFICIENT_EVIDENCE",
                "customer_summary": "No customer records or policy documents could be retrieved.",
                "identified_root_cause": "Cannot determine complaint context due to absence of retrieved data.",
                "recommendation": None,
                "rationale": "Retrieved evidence contained neither past tickets nor applicable policies. FlowMind policy prohibits unsubstantiated actions.",
                "citations": [],
                "confidence_score": 0.0,
                "requires_human_approval": False,
                "indirect_injection_detected": injection_detected,
            })

        if has_no_tickets:
            return json.dumps({
                "status": "ABSTAINED",
                "abstention_reason": "INSUFFICIENT_EVIDENCE",
                "customer_summary": "Customer ticket history could not be found in the knowledge base.",
                "identified_root_cause": "Lack of ticket history prevents verifying complaint veracity or repeat contact status.",
                "recommendation": None,
                "rationale": "Although policy documents were located, no matching customer ticket history was found. Abstaining per responsible AI guidelines.",
                "citations": self._extract_policy_citations(prompt),
                "confidence_score": 0.2,
                "requires_human_approval": False,
                "indirect_injection_detected": injection_detected,
            })

        # 3. Check for contradictory evidence (only inside content_to_check, NOT prompt instructions)
        if "conflicting resolution" in content_to_check or "status=resolved but customer states open" in content_to_check or "contradictory ticket" in content_to_check:
            return json.dumps({
                "status": "ABSTAINED",
                "abstention_reason": "CONTRADICTORY_EVIDENCE",
                "customer_summary": "Retrieved records present conflicting status information.",
                "identified_root_cause": "Customer records indicate mutually contradictory ticket resolution states.",
                "recommendation": {
                    "action_type": "REQUEST_CUSTOMER_INFO",
                    "target_team": "Customer Success Team",
                    "urgency": "medium",
                    "parameters": {"clarification_needed": "Verify current resolution status directly with customer"},
                    "requires_approval": True,
                },
                "rationale": "Conflicting records prevent definitive escalation routing. Abstaining from automated routing pending human clarification.",
                "citations": self._extract_ticket_citations(prompt) + self._extract_policy_citations(prompt),
                "confidence_score": 0.4,
                "requires_human_approval": True,
                "indirect_injection_detected": injection_detected,
            })

        # 4. Check for ambiguous complaint
        if is_empty_or_vague or "ambiguous complaint" in content_to_check:
            return json.dumps({
                "status": "ABSTAINED",
                "abstention_reason": "AMBIGUOUS_COMPLAINT",
                "customer_summary": "The customer inquiry lacks specific order, ticket, or defect identifiers.",
                "identified_root_cause": "Insufficient specificity in complaint description.",
                "recommendation": None,
                "rationale": "The customer complaint description does not contain actionable details to cross-reference with policies.",
                "citations": self._extract_ticket_citations(prompt)[:1],
                "confidence_score": 0.25,
                "requires_human_approval": False,
                "indirect_injection_detected": injection_detected,
            })

        # 5. Extract facts from retrieved context
        ticket_citations = self._extract_ticket_citations(prompt)
        policy_citations = self._extract_policy_citations(prompt)
        all_citations = ticket_citations + policy_citations

        # Separate ticket evidence from policy evidence to avoid keyword pollution
        ticket_evidence = ""
        t_match = re.search(
            r"=== section 1: retrieved customer ticket history ===(.*?)(?==== section 2:|\Z)",
            evidence_block,
            re.DOTALL | re.IGNORECASE,
        )
        if t_match:
            ticket_evidence = t_match.group(1)
        else:
            # Fallback for raw prompts or test fixtures without section headers
            p_split = re.split(r"(?:=== section 2:|---\s*\[policy)", evidence_block, flags=re.IGNORECASE)
            ticket_evidence = p_split[0]

        ticket_facts = f"{issue_summary_lower}\n{ticket_evidence}"
        category = self._determine_category(issue_summary_lower, ticket_evidence)

        # Check conditions against customer ticket facts (not policy text)
        is_legal_threat = any(term in ticket_facts for term in ["legal action", "lawyer", "regulatory", "attorney", "court"])
        is_high_amount = any(term in ticket_facts for term in ["$1,450", "1450", "> $1000", "greater than $1000", "greater than $500", "> $500", "$1000 threshold"])
        is_sla_breach = "sla_breach: true" in ticket_facts or "exceeded its sla" in ticket_facts or "sla breach" in ticket_facts or "past deadline" in ticket_facts
        is_repeat = any(term in ticket_facts for term in ["fourth time", "third time", "repeated", "repeat contact", "multiple times", "4+ tickets", "3 or more"])
        is_high_priority = "priority: high" in ticket_facts or "priority=high" in ticket_facts or "priority: 'high'" in ticket_facts
        is_refund = any(term in ticket_facts for term in ["refund", "double charge", "charged twice", "billing dispute", "overcharge"])
        is_rerouting = "re-routing" in ticket_facts or "wrong team" in ticket_facts

        # Determine Category & Routing
        if is_legal_threat:
            action_type = "ESCALATE_TICKET"
            target_team = "Legal & Compliance Team"
            level = "L3"
            urgency = "critical"
            rationale = "Customer explicitly cited legal/regulatory action. Per Escalation Policy Section 'Escalation Levels', legal threats trigger L3 escalation and require routing to Legal & Compliance Team."
        elif is_high_amount and category == "billing":
            action_type = "ESCALATE_TICKET"
            target_team = "Finance & Compliance Team"
            level = "L2"
            urgency = "high"
            rationale = "Disputed amount exceeds the high-financial-impact threshold ($1,000 / $500). Per Escalation Policy Trigger 6 and Team Routing Policy Special Cases, billing disputes over $1,000 must route to Finance & Compliance Team for L2 review."
        elif is_rerouting:
            action_type = "TRANSFER_TEAM"
            target_team = self._get_primary_team(category)
            level = None
            urgency = "medium"
            rationale = "Ticket issue category does not match the currently assigned team. Per Team Routing Policy, transferring ticket to primary responsible team."
        elif is_sla_breach and (is_high_priority or is_repeat):
            action_type = "ESCALATE_TICKET"
            target_team = self._get_escalation_team(category)
            level = "L2"
            urgency = "high"
            rationale = "Ticket exhibits an active SLA breach combined with high priority/repeat contacts. Per Escalation Policy, high-priority tickets with SLA breach go directly to L2 Team Manager review."
        elif is_repeat:
            action_type = "ESCALATE_TICKET"
            target_team = self._get_escalation_team(category)
            level = "L2"
            urgency = "high"
            rationale = "Customer has contacted support multiple times for the same recurring issue without permanent resolution. Per Escalation Policy Trigger 2 (Repeat Contact), this necessitates L2 escalation."
        elif is_sla_breach:
            action_type = "ESCALATE_TICKET"
            target_team = self._get_primary_team(category)
            level = "L1"
            urgency = "high"
            rationale = "Ticket has exceeded agreed resolution SLA window. Per Escalation Policy Trigger 1, an active SLA breach mandates L1 escalation to Senior Support Agent."
        elif is_refund and ("dispute" in content_to_check or "charged twice" in content_to_check):
            action_type = "ISSUE_REFUND_RECOMMENDATION"
            target_team = "Finance & Compliance Team"
            level = "L1"
            urgency = "medium"
            rationale = "Retrieved records indicate a verified duplicate billing transaction. Per Refund Policy, duplicate payments are eligible for full refund upon supervisor confirmation."
        elif "damaged" in ticket_facts:
            action_type = "ESCALATE_TICKET"
            target_team = self._get_primary_team(category)
            level = "L1"
            urgency = "medium"
            rationale = "Customer reported physical delivery damage. Escalating to primary Logistics Team for damage verification and replacement handling."
        else:
            action_type = "RESOLVE_STANDARD"
            target_team = self._get_primary_team(category)
            level = None
            urgency = "low"
            rationale = "Investigation shows single occurrence within standard SLA boundaries. Standard support resolution procedures apply."

        # If injection was detected, explicitly highlight defense in rationale
        if injection_detected:
            rationale += " [Security Notice: Adversarial prompt instructions were detected in retrieved ticket contents and disregarded per indirect injection defense protocol.]"

        return json.dumps({
            "status": "RECOMMENDATION_READY",
            "abstention_reason": None,
            "customer_summary": "Customer inquiry investigated across past ticket history and organizational policies.",
            "identified_root_cause": "Identified operational breakdown or service failure documented in retrieved ticket evidence.",
            "recommendation": {
                "action_type": action_type,
                "target_team": target_team,
                "escalation_level": level,
                "urgency": urgency,
                "parameters": {
                    "routing_rationale": rationale,
                    "target_team": target_team,
                },
                "requires_approval": True,
            },
            "rationale": rationale,
            "citations": all_citations,
            "confidence_score": 0.88 if not injection_detected else 0.82,
            "requires_human_approval": True,
            "indirect_injection_detected": injection_detected,
        })

    def _extract_ticket_citations(self, prompt: str) -> List[Dict[str, Any]]:
        citations = []
        matches = re.findall(r"\[Ticket\s+([A-Za-z0-9\-]+),\s*chunk\s*(\d+)\]", prompt)
        seen = set()
        for t_id, c_idx in matches:
            key = (t_id, int(c_idx))
            if key not in seen:
                seen.add(key)
                citations.append({
                    "source_type": "ticket",
                    "source_id": t_id,
                    "chunk_index": int(c_idx),
                    "snippet": f"Historical ticket record {t_id}",
                    "relevance_reason": "Provides historical customer complaint records and issue patterns",
                })
        return citations

    def _extract_policy_citations(self, prompt: str) -> List[Dict[str, Any]]:
        citations = []
        matches = re.findall(r"\[Policy:\s*([A-Za-z0-9_\-\.]+),\s*chunk\s*(\d+)\]", prompt)
        seen = set()
        for p_id, c_idx in matches:
            key = (p_id, int(c_idx))
            if key not in seen:
                seen.add(key)
                citations.append({
                    "source_type": "policy",
                    "source_id": p_id,
                    "chunk_index": int(c_idx),
                    "snippet": f"Policy document {p_id}",
                    "relevance_reason": "Defines governing escalation triggers and routing policies",
                })
        return citations

    def _determine_category(self, request_text: str, ticket_text: str) -> str:
        combined = f"{request_text} {ticket_text}".lower()
        if any(w in combined for w in ["delivery", "damaged goods", "shipping", "package"]):
            return "delivery"
        if any(w in combined for w in ["billing", "charged", "invoice", "refund", "duplicate charge", "overcharge"]):
            return "billing"
        if any(w in combined for w in ["product_defect", "defect", "broken", "device", "quality"]):
            return "product_defect"
        if any(w in combined for w in ["account_access", "password", "login", "locked out", "access"]):
            return "account_access"
        return "service_quality"

    def _get_primary_team(self, category: str) -> str:
        if category == "billing":
            return "Billing Team"
        if category == "delivery":
            return "Logistics Team"
        if category == "product_defect":
            return "Quality Team"
        if category == "account_access":
            return "IT Support Team"
        return "Customer Success Team"

    def _get_escalation_team(self, category: str) -> str:
        if category == "billing":
            return "Finance & Compliance Team"
        if category == "delivery":
            return "Operations Manager"
        if category == "product_defect":
            return "Engineering Team"
        if category == "account_access":
            return "Security Team"
        return "People & Culture Team"

    def _generate_baseline_plain_answer(self, prompt: str) -> str:
        """Generate a plain conversational answer summarizing retrieved chunks with citations."""
        citations = self._extract_ticket_citations(prompt) + self._extract_policy_citations(prompt)
        citation_labels = [c["source_id"] for c in citations]
        cit_str = ", ".join(citation_labels) if citation_labels else "the knowledge base"

        if not citations and "[no relevant documents found]" in prompt.lower():
            return "I could not find any relevant information in the knowledge base to answer your question."

        return (
            f"Based on evidence from {cit_str}, the customer inquiry pertains to documented support tickets and policies. "
            f"Please refer to the cited documentation for specific guidance on this issue."
        )


# ============================================================
# Anthropic Claude Provider
# ============================================================

class AnthropicLLMProvider(LLMProvider):
    """
    Claude provider using Anthropic Python SDK.
    Requires ANTHROPIC_API_KEY environment variable.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Set it in .env or pass it to AnthropicLLMProvider."
            )
        self.model = model or os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20241022")

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is not installed. Install it with: pip install anthropic"
            )

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.0) -> str:
        """Call Claude API and return text response."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        # Extract text from content blocks
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        return "\n".join(text_blocks)


# ============================================================
# Provider Factory
# ============================================================

def get_llm_provider(provider_type: Optional[str] = None) -> LLMProvider:
    """
    Factory function returning the configured LLMProvider instance.
    Defaults to MockLLMProvider when provider is 'mock' or when ANTHROPIC_API_KEY is missing.
    """
    choice = provider_type or os.environ.get("LLM_PROVIDER", "").lower()

    if choice == "anthropic":
        return AnthropicLLMProvider()

    # If ANTHROPIC_API_KEY is explicitly present and choice is not explicitly 'mock', use Anthropic
    if os.environ.get("ANTHROPIC_API_KEY") and choice != "mock":
        try:
            return AnthropicLLMProvider()
        except Exception as e:
            logger.warning("Failed to initialize Anthropic provider (%s), falling back to mock.", e)
            return MockLLMProvider()

    return MockLLMProvider()
