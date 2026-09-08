"""
FlowMind AI - Reasoning Engine (Phase 2)
Coordinates evidence retrieval, prompt injection defense, LLM reasoning,
strict citation integrity verification, and human-approval gating for
the Customer Complaint Escalation workflow.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from backend.reasoning.llm_provider import LLMProvider, get_llm_provider
from backend.reasoning.models import (
    AbstentionReason,
    ActionType,
    ComplaintInvestigationRequest,
    EvidenceCitation,
    NextBestAction,
    ReasoningOutput,
)
from backend.reasoning.prompts import (
    ENTERPRISE_SYSTEM_PROMPT,
    build_investigation_prompt,
)
from backend.retrieval.models import MetadataFilter, RetrievalQuery, RetrievalResult
from backend.retrieval.retriever import retrieve as default_retrieve

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Evidence-grounded decision support engine for Customer Complaint Escalation.
    """

    def __init__(
        self,
        retriever_fn: Optional[Callable[[RetrievalQuery], RetrievalResult]] = None,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.retrieve = retriever_fn or default_retrieve
        self.llm_provider = llm_provider or get_llm_provider()

    def investigate(self, request: ComplaintInvestigationRequest) -> ReasoningOutput:
        """
        Execute an end-to-end investigation of a customer complaint:
          1. Retrieve past tickets for customer / issue.
          2. Retrieve governing enterprise policies.
          3. Guard against indirect prompt injection.
          4. Invoke LLM for grounded reasoning.
          5. Verify citation integrity against actually retrieved chunks.
          6. Enforce human-approval gating on sensitive actions.
        """
        t0 = time.perf_counter()

        # Step 1: Pre-retrieval dual-path queries
        ticket_result = self._retrieve_tickets(request)
        policy_result = self._retrieve_policies(request)

        total_chunks = len(ticket_result.chunks) + len(policy_result.chunks)
        retrieval_ms = ticket_result.retrieval_time_ms + policy_result.retrieval_time_ms

        retrieval_summary = {
            "ticket_chunks_retrieved": len(ticket_result.chunks),
            "policy_chunks_retrieved": len(policy_result.chunks),
            "total_retrieved": total_chunks,
            "retrieval_latency_ms": round(retrieval_ms, 2),
            "ticket_citations_available": ticket_result.citations,
            "policy_citations_available": policy_result.citations,
        }

        # Step 2: Early Abstention if zero evidence retrieved
        if total_chunks == 0:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return ReasoningOutput(
                status="ABSTAINED",
                abstention_reason=AbstentionReason.INSUFFICIENT_EVIDENCE,
                customer_summary="No relevant ticket history or policies were located.",
                identified_root_cause="Absence of retrieved context prevents evidence-grounded reasoning.",
                recommendation=None,
                rationale="FlowMind AI strictly prohibits unsubstantiated actions without retrieved evidence.",
                citations=[],
                confidence_score=0.0,
                requires_human_approval=False,
                indirect_injection_detected=False,
                retrieval_summary=retrieval_summary,
                reasoning_time_ms=round(elapsed_ms, 2),
                model_used=self.llm_provider.__class__.__name__,
            )

        # Step 3: Sandboxed Prompt Construction
        ticket_context = ticket_result.combined_context
        policy_context = policy_result.combined_context
        user_prompt = build_investigation_prompt(
            customer_id=request.customer_id,
            customer_name=request.customer_name,
            issue_summary=request.issue_summary,
            ticket_context=ticket_context,
            policy_context=policy_context,
        )

        # Step 4: LLM Generation with JSON retry mechanism
        raw_response = self.llm_provider.generate(
            prompt=user_prompt,
            system_prompt=ENTERPRISE_SYSTEM_PROMPT,
            temperature=0.0,
        )

        parse_error: Optional[str] = None
        output_data: Optional[Dict[str, Any]] = None
        try:
            output_data = self._parse_and_validate_json(raw_response)
        except ValueError as e:
            parse_error = str(e)
            logger.warning("First LLM JSON generation failed (%s). Attempting retry with correction prompt...", parse_error)

        # Retry once if parsing or validation failed
        if parse_error is not None:
            retry_prompt = (
                f"{user_prompt}\n\n"
                f"=== PREVIOUS ATTEMPT FAILED WITH ERROR ===\n"
                f"{parse_error}\n\n"
                f"PREVIOUS RAW OUTPUT:\n"
                f"{raw_response[:500]}\n\n"
                f"=== INSTRUCTION ===\n"
                f"Your previous output failed JSON syntax or schema validation. "
                f"Please correct the output and return strictly valid JSON conforming to the schema."
            )
            retry_response = self.llm_provider.generate(
                prompt=retry_prompt,
                system_prompt=ENTERPRISE_SYSTEM_PROMPT,
                temperature=0.0,
            )
            try:
                output_data = self._parse_and_validate_json(retry_response)
                parse_error = None
            except ValueError as e2:
                parse_error = f"Retry attempt failed: {e2}"
                logger.error("LLM JSON retry failed: %s", parse_error)

        # If both attempts failed, return status="ERROR"
        if parse_error is not None or output_data is None:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return ReasoningOutput(
                status="ERROR",
                abstention_reason=None,
                customer_summary="Error parsing model response.",
                identified_root_cause=f"Model output failed JSON parsing after retry: {parse_error}",
                recommendation=None,
                rationale=f"Model did not return valid JSON adhering to schema after retry. Error: {parse_error}",
                citations=[],
                confidence_score=0.0,
                requires_human_approval=False,
                indirect_injection_detected=False,
                retrieval_summary=retrieval_summary,
                reasoning_time_ms=round(elapsed_ms, 2),
                model_used=self.llm_provider.__class__.__name__,
            )

        # Step 5: Post-generation citation integrity verification
        valid_chunk_keys = self._collect_valid_chunk_keys(ticket_result, policy_result)
        valid_source_ids = {k[1] for k in valid_chunk_keys}
        verified_citations, stripped_source_ids = self._verify_citations(
            output_data.get("citations", []), valid_chunk_keys
        )

        # Step 6: Cross-check rationale text for stripped or unretrieved citation references
        raw_rationale = output_data.get("rationale", "")
        hallucinated_refs = self._detect_unretrieved_references_in_text(
            raw_rationale, valid_source_ids, stripped_source_ids
        )

        status_str = output_data.get("status", "RECOMMENDATION_READY")
        abstention_reason_val = output_data.get("abstention_reason")
        abstention_reason = (
            AbstentionReason(abstention_reason_val) if abstention_reason_val else None
        )

        # If rationale references unretrieved or stripped evidence, downgrade to CITATION_INTEGRITY_FAILURE
        if hallucinated_refs:
            logger.warning(
                "Rationale referenced unretrieved source(s) %s. Downgrading to CITATION_INTEGRITY_FAILURE.",
                hallucinated_refs,
            )
            status_str = "ABSTAINED"
            abstention_reason = AbstentionReason.CITATION_INTEGRITY_FAILURE
            recommendation_dict = None
            final_rationale = (
                f"[Abstained due to citation integrity violation: Rationale referenced unretrieved evidence ({', '.join(sorted(hallucinated_refs))})]. "
                f"Original rationale: {raw_rationale}"
            )
        else:
            final_rationale = raw_rationale
            recommendation_dict = output_data.get("recommendation")

        # Step 7: Enforce Approval Gating & Non-Negotiables
        recommendation_obj: Optional[NextBestAction] = None

        if recommendation_dict and status_str != "ABSTAINED":
            # Enforce requires_approval = True for sensitive operations
            action_type_str = recommendation_dict.get("action_type", "ESCALATE_TICKET")
            recommendation_obj = NextBestAction(
                action_type=ActionType(action_type_str),
                target_team=recommendation_dict.get("target_team", "Support Team"),
                escalation_level=recommendation_dict.get("escalation_level"),
                urgency=recommendation_dict.get("urgency", "medium"),
                parameters=recommendation_dict.get("parameters", {}),
                requires_approval=True,  # Non-negotiable constraint
            )

        # Ensure consistency: if recommendation is None and not already marked ABSTAINED, mark ABSTAINED
        if not recommendation_obj and status_str != "ABSTAINED":
            status_str = "ABSTAINED"
            abstention_reason = abstention_reason or AbstentionReason.INSUFFICIENT_EVIDENCE

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return ReasoningOutput(
            status=status_str,
            abstention_reason=abstention_reason,
            customer_summary=output_data.get("customer_summary", ""),
            identified_root_cause=output_data.get("identified_root_cause", ""),
            recommendation=recommendation_obj,
            rationale=final_rationale,
            citations=verified_citations,
            confidence_score=float(output_data.get("confidence_score", 0.8)) if not hallucinated_refs else 0.0,
            requires_human_approval=True if recommendation_obj else False,
            indirect_injection_detected=bool(output_data.get("indirect_injection_detected", False)),
            retrieval_summary=retrieval_summary,
            reasoning_time_ms=round(elapsed_ms, 2),
            model_used=self.llm_provider.__class__.__name__,
        )

    # ------------------------------------------------------------------
    # Retrieval Helpers
    # ------------------------------------------------------------------

    def _retrieve_tickets(self, request: ComplaintInvestigationRequest) -> RetrievalResult:
        """Query past tickets matching the customer or issue description."""
        query_text = request.issue_summary
        if request.customer_name:
            query_text = f"{request.customer_name} {query_text}"

        query = RetrievalQuery(
            query_text=query_text,
            top_k=request.top_k_tickets,
            filters=MetadataFilter(source_type="ticket"),
            score_threshold=0.25,
        )
        try:
            return self.retrieve(query)
        except Exception as e:
            logger.warning("Ticket retrieval failed (%s), returning empty result.", e)
            return RetrievalResult(
                query_text=query_text,
                chunks=[],
                total_found=0,
                filters_applied={"source_type": "ticket"},
                retrieval_time_ms=0.0,
            )

    def _retrieve_policies(self, request: ComplaintInvestigationRequest) -> RetrievalResult:
        """Query policy documents for escalation, SLA, routing, and refund guidelines."""
        query_text = f"escalation policy SLA guidelines team routing refund rules {request.issue_summary}"
        query = RetrievalQuery(
            query_text=query_text,
            top_k=request.top_k_policies,
            filters=MetadataFilter(source_type="policy"),
            score_threshold=0.25,
        )
        try:
            return self.retrieve(query)
        except Exception as e:
            logger.warning("Policy retrieval failed (%s), returning empty result.", e)
            return RetrievalResult(
                query_text=query_text,
                chunks=[],
                total_found=0,
                filters_applied={"source_type": "policy"},
                retrieval_time_ms=0.0,
            )

    # ------------------------------------------------------------------
    # Parsing & Verification
    # ------------------------------------------------------------------

    def _parse_and_validate_json(self, raw_text: str) -> Dict[str, Any]:
        """Strip markdown fences and parse structured JSON. Raises ValueError on error."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except Exception:
                    raise ValueError(f"Malformed JSON: {err}")
            else:
                raise ValueError(f"Malformed JSON: {err}")

        if not isinstance(data, dict):
            raise ValueError("Parsed JSON is not an object")

        if "status" not in data:
            raise ValueError("Missing required field 'status'")

        return data

    def _collect_valid_chunk_keys(
        self, ticket_result: RetrievalResult, policy_result: RetrievalResult
    ) -> Set[Tuple[str, str, int]]:
        """Collect the set of actually retrieved (source_type, source_id, chunk_index)."""
        valid = set()
        for c in ticket_result.chunks:
            valid.add((c.source_type, c.source_id, c.chunk_index))
            # Also allow fuzzy chunk match on source_id alone
            valid.add((c.source_type, c.source_id, -1))
        for c in policy_result.chunks:
            valid.add((c.source_type, c.source_id, c.chunk_index))
            valid.add((c.source_type, c.source_id, -1))
        return valid

    def _verify_citations(
        self, citations_raw: List[Dict[str, Any]], valid_keys: Set[Tuple[str, str, int]]
    ) -> Tuple[List[EvidenceCitation], Set[str]]:
        """Filter out hallucinated citations and return verified citations + stripped source IDs."""
        verified: List[EvidenceCitation] = []
        stripped_source_ids: Set[str] = set()

        for c in citations_raw:
            source_type = c.get("source_type", "")
            source_id = c.get("source_id", "")
            chunk_index = int(c.get("chunk_index", 0))

            # Verify presence in valid retrieved set (exact or by source_id)
            if (source_type, source_id, chunk_index) in valid_keys or (source_type, source_id, -1) in valid_keys:
                verified.append(
                    EvidenceCitation(
                        source_type=source_type,
                        source_id=source_id,
                        chunk_index=chunk_index,
                        snippet=c.get("snippet", ""),
                        relevance_reason=c.get("relevance_reason", ""),
                    )
                )
            else:
                stripped_source_ids.add(source_id)
                logger.warning(
                    "Suppressed hallucinated citation: %s:%s (not in retrieved set)",
                    source_type, source_id,
                )
        return verified, stripped_source_ids

    def _detect_unretrieved_references_in_text(
        self, text: str, valid_source_ids: Set[str], stripped_source_ids: Set[str]
    ) -> Set[str]:
        """Cross-check rationale text to ensure it does not mention stripped or unretrieved source IDs."""
        hallucinated = set()

        # 1. Any source_id explicitly stripped from the citations list
        for sid in stripped_source_ids:
            if sid and sid.lower() in text.lower():
                hallucinated.add(sid)

        # 2. Any ticket ID pattern (e.g. TKT-1234 or Ticket #1234) in text not in valid_source_ids
        ticket_matches = re.findall(r"\bTKT-([A-Za-z0-9\-]+)\b", text, re.IGNORECASE)
        for num in ticket_matches:
            full_id = f"TKT-{num}"
            # Check case-insensitive against valid IDs
            if not any(v.lower() == full_id.lower() for v in valid_source_ids):
                hallucinated.add(full_id)

        # 3. Any policy markdown references (e.g. some_policy.md) not in valid_source_ids
        policy_matches = re.findall(r"\b([a-zA-Z_0-9\-]+\.md)\b", text, re.IGNORECASE)
        for p_file in policy_matches:
            if not any(v.lower() == p_file.lower() for v in valid_source_ids):
                hallucinated.add(p_file)

        return hallucinated


# ============================================================
# Convenience Function
# ============================================================

def investigate_complaint(
    request: ComplaintInvestigationRequest,
    retriever_fn: Optional[Callable[[RetrievalQuery], RetrievalResult]] = None,
    llm_provider: Optional[LLMProvider] = None,
) -> ReasoningOutput:
    """Convenience function to run a complaint investigation."""
    engine = ReasoningEngine(retriever_fn=retriever_fn, llm_provider=llm_provider)
    return engine.investigate(request)


if __name__ == "__main__":
    # Quick dry-run demonstration
    sample_request = ComplaintInvestigationRequest(
        customer_id="CUST-1002",
        customer_name="Arjun Sharma",
        issue_summary="Customer reports damaged goods for the fourth time. Threatening to cancel subscription.",
    )
    result = investigate_complaint(sample_request)
    print("\n=== FLOWMIND AI REASONING OUTPUT (DRY RUN) ===")
    print(f"Status: {result.status}")
    print(f"Confidence: {result.confidence_score}")
    print(f"Human Approval Required: {result.requires_human_approval}")
    if result.recommendation:
        print(f"Action: {result.recommendation.action_type}")
        print(f"Target Team: {result.recommendation.target_team}")
        print(f"Escalation Level: {result.recommendation.escalation_level}")
        print(f"Urgency: {result.recommendation.urgency}")
    print(f"Rationale: {result.rationale}")
    print(f"Citations: {result.citation_labels}")
    print(f"Injection Detected: {result.indirect_injection_detected}")
    print(f"Reasoning Time: {result.reasoning_time_ms} ms")
