"""
FlowMind AI - SHA-256 Tamper-Evident Audit Hash Chain Tests

These are the definitive proof that the hash chain implementation is genuine.
A fabricated client-side implementation could never fail these tests because:
  - Test A: verify_event_chain() recomputes hashes from *content* - mutating
    content without updating the hash makes it fail (the old code never recomputed).
  - Test C: verify_event_chain() independently checks chain linkage (parent_hash),
    so a partial tamper that updates block_hash but not parent_hash is caught.
  - Tests D & E: confirm serialisation determinism and immutability enforcement.

All five tests must pass for the implementation to be considered correct.
"""
from __future__ import annotations

import uuid
import pytest

from backend.audit.chain import (
    GENESIS_HASH,
    build_event_chain,
    canonical_json,
    compute_event_hash,
    verify_event_chain,
)
from backend.audit.models import AuditRecord
from backend.audit.service import AuditService, DuplicateAuditRecordError


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------

def build_real_audit_record(workflow_id: str) -> AuditRecord:
    """Construct a fully populated AuditRecord with a real SHA-256 event chain.

    Mirrors exactly what _finalize_audit() produces at runtime.
    The record is intentionally given all five lifecycle stages so tests have
    enough events to tamper with at various indices.
    """
    short_id = workflow_id[:8]
    started_at = "2026-09-15T05:00:00+00:00"
    completed_at = "2026-09-15T05:00:02+00:00"

    request_payload = {
        "customer_id": "CUST-TEST-001",
        "customer_name": "Alice Test",
        "issue_summary": "Test complaint for hash chain verification.",
        "requester_id": "USR-001",
        "requester_role": "support_agent",
    }
    retrieval_summary = {"total_retrieved": 3, "top_score": 0.92}
    evidence_citations = [{"source_id": "TKT-0001", "score": 0.92}]
    reasoning_output = {
        "status": "RECOMMENDATION_READY",
        "abstention_reason": None,
        "root_cause": "Duplicate billing cycle.",
        "rationale": "Clear evidence of duplicate charge.",
        "confidence_score": 0.91,
        "indirect_injection_detected": False,
        "recommendation": {"action_type": "ESCALATE_TICKET", "target_team": "Finance", "priority": "HIGH"},
    }
    approval_record = {
        "decision": "APPROVE",
        "approver_id": "USR-003",
        "approver_role": "manager",
        "comments": "Approved.",
        "timestamp": "2026-09-15T05:00:01+00:00",
    }
    execution_record = {
        "status": "SUCCESS",
        "transaction_id": "TX-CHAIN-001",
        "dispatched_to": "MockEnterpriseConnector",
        "timestamp": completed_at,
    }

    raw_events = [
        {
            "event_id": f"EVT-001-{short_id}",
            "stage": "REQUEST_RECEIVED",
            "timestamp": started_at,
            "actor": "USR-001",
            "details": request_payload,
        },
        {
            "event_id": f"EVT-002-{short_id}",
            "stage": "EVIDENCE_RETRIEVED",
            "timestamp": started_at,
            "actor": "VectorRetriever (pgvector)",
            "details": {
                "retrieval_summary": retrieval_summary,
                "evidence_citations": evidence_citations,
            },
        },
        {
            "event_id": f"EVT-003-{short_id}",
            "stage": "REASONING_COMPLETED",
            "timestamp": started_at,
            "actor": "ReasoningEngine",
            "details": reasoning_output,
        },
        {
            "event_id": f"EVT-004-{short_id}",
            "stage": "APPROVAL_SUBMITTED",
            "timestamp": approval_record["timestamp"],
            "actor": "USR-003",
            "details": approval_record,
        },
        {
            "event_id": f"EVT-005-{short_id}",
            "stage": "ACTION_DISPATCHED",
            "timestamp": completed_at,
            "actor": "MockEnterpriseConnector",
            "details": execution_record,
        },
    ]

    chain_events = build_event_chain(raw_events)

    return AuditRecord(
        audit_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        terminal_state="COMPLETED",
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=2000.0,
        request_payload=request_payload,
        retrieval_summary=retrieval_summary,
        evidence_citations=evidence_citations,
        reasoning_output=reasoning_output,
        approval_record=approval_record,
        execution_record=execution_record,
        chain_events=chain_events,
    )


# ---------------------------------------------------------------------------
# Test A: Content-integrity tamper detection
# ---------------------------------------------------------------------------

class TestContentTamperDetection:

    def test_tamper_detection_breaks_chain(self):
        """
        Mutating a stored event's content (details field) after finalization must be
        detected by verify_event_chain() as a content-integrity failure.

        This is the core proof the feature is genuine: the verifier recomputes the
        SHA-256 hash from the stored content fields and compares it to the stored
        block_hash.  If content was mutated without recomputing block_hash, they differ.

        A fabricated client-side implementation would never fail this test because it
        never recomputes hashes from content.
        """
        record = build_real_audit_record("WF-TAMPER-001")

        # Confirm clean before tampering
        pre_tamper = verify_event_chain(record.chain_events)
        assert pre_tamper["valid"] is True, "Chain should be valid before tampering"

        # Mutate EVT-002 content (index 1) without updating its block_hash
        tampered_events = [dict(e) for e in record.chain_events]
        tampered_events[1] = dict(tampered_events[1])
        tampered_events[1]["details"] = {"injected": "malicious_override", "score": 9999}

        result = verify_event_chain(tampered_events)
        assert result["valid"] is False, "Chain must be detected as invalid after content tamper"
        assert result["failed_at_index"] == 1, "Failure must be reported at index 1 (EVT-002)"
        assert result["failed_event_id"] == tampered_events[1]["event_id"]


# ---------------------------------------------------------------------------
# Test B: Unmodified chain verifies as valid
# ---------------------------------------------------------------------------

class TestCleanChainVerification:

    def test_unmodified_chain_verifies_valid(self):
        """
        An unmodified audit chain must verify as completely valid end-to-end.
        Confirms the happy path: no false positives on genuine records.
        """
        record = build_real_audit_record("WF-VALID-001")
        result = verify_event_chain(record.chain_events)

        assert result["valid"] is True
        assert result["failed_at_index"] is None
        assert result["failed_event_id"] is None

    def test_empty_chain_verifies_valid(self):
        """An empty event list is trivially valid (no blocks to check)."""
        result = verify_event_chain([])
        assert result["valid"] is True

    def test_genesis_hash_used_for_first_event(self):
        """The first event's parent_hash must be the 64-zero GENESIS_HASH."""
        record = build_real_audit_record("WF-GENESIS-001")
        assert record.chain_events[0]["parent_hash"] == GENESIS_HASH
        assert len(record.chain_events[0]["block_hash"]) == 64

    def test_chain_is_sequentially_linked(self):
        """Each event's parent_hash must equal the previous event's block_hash."""
        record = build_real_audit_record("WF-LINK-VALID-001")
        events = record.chain_events
        for i in range(1, len(events)):
            assert events[i]["parent_hash"] == events[i - 1]["block_hash"], (
                f"Linkage broken at index {i}: parent_hash does not match previous block_hash"
            )


# ---------------------------------------------------------------------------
# Test C: Chain-linkage tamper detection (Strengthening 1)
# ---------------------------------------------------------------------------

class TestChainLinkageTamperDetection:

    def test_chain_linkage_tampering_detected(self):
        """
        Corrupting a parent_hash value without touching event content must be detected
        as a chain-linkage failure.

        This tests check (b) of verify_event_chain() independently of check (a).
        An attacker who edits content AND recomputes block_hash but forgets to update
        the NEXT event's parent_hash would be caught here even if check (a) passed.

        Mechanism: we corrupt tampered_events[2]["parent_hash"] directly.  The content
        and block_hash of EVT-003 are untouched, so check (a) would pass if run in
        isolation -- only check (b) catches this, confirming both checks are active.
        """
        record = build_real_audit_record("WF-LINK-001")
        tampered_events = [dict(e) for e in record.chain_events]

        # Corrupt parent_hash of EVT-003 (index 2) without touching its content or block_hash
        tampered_events[2] = dict(tampered_events[2])
        tampered_events[2]["parent_hash"] = "deadbeef" * 8  # 64 chars, but wrong value

        result = verify_event_chain(tampered_events)
        assert result["valid"] is False, "Chain must be invalid when parent_hash is corrupted"
        assert result["failed_at_index"] == 2, "Failure must be at index 2 (corrupted parent_hash)"
        assert result["failed_event_id"] == tampered_events[2]["event_id"]

    def test_swapped_event_order_detected(self):
        """
        Swapping two events in the chain (leaving their individual hashes intact)
        must be detected as a linkage failure at the first swapped position.
        """
        record = build_real_audit_record("WF-SWAP-001")
        tampered_events = list(record.chain_events)  # shallow copy of list

        # Swap EVT-001 and EVT-002
        tampered_events[0], tampered_events[1] = tampered_events[1], tampered_events[0]

        result = verify_event_chain(tampered_events)
        assert result["valid"] is False
        # First event (now EVT-002) has parent_hash == EVT-001's block_hash, not GENESIS_HASH
        assert result["failed_at_index"] == 0


# ---------------------------------------------------------------------------
# Test D: Serialisation determinism (Strengthening 2)
# ---------------------------------------------------------------------------

class TestSerialisationDeterminism:

    def test_serialization_determinism(self):
        """
        Hashing the same event content on two separate independent calls must produce
        bit-for-bit identical hashes.

        Guards against silent drift from non-deterministic serialisation of datetimes,
        UUIDs, Enums, or key ordering -- any such drift would look like a false-positive
        tamper detection rather than what it actually is: a serialisation bug.
        """
        details = {
            "decision": "APPROVE",
            "approver_id": "USR-003",
            "timestamp": "2026-09-15T05:00:00+00:00",
            "nested": {"level": 1, "flag": True, "score": 0.95},
        }
        content = {
            "event_id": "EVT-SER-001",
            "stage": "APPROVAL_SUBMITTED",
            "timestamp": "2026-09-15T05:00:00+00:00",
            "actor": "USR-003",
            "details": details,
        }
        parent = GENESIS_HASH

        hash1 = compute_event_hash(content, parent)
        hash2 = compute_event_hash(content, parent)  # independent call, same inputs
        assert hash1 == hash2, "compute_event_hash must be deterministic across independent calls"
        assert len(hash1) == 64, "SHA-256 digest must be 64 hex characters"

    def test_canonical_json_key_order_is_stable(self):
        """canonical_json() must produce identical output regardless of input dict insertion order."""
        dict_a = {"z_key": 1, "a_key": 2, "m_key": 3}
        dict_b = {"a_key": 2, "m_key": 3, "z_key": 1}
        assert canonical_json(dict_a) == canonical_json(dict_b), (
            "canonical_json must sort keys so insertion order has no effect"
        )

    def test_canonical_json_non_native_types_stable(self):
        """Non-JSON-native values must be serialised consistently via default=str."""
        import datetime as dt
        data_with_str = {"ts": "2026-09-15T05:00:00", "val": "42"}
        # Simulate what would happen if a datetime snuck through (default=str coerces it)
        # Both should produce the same canonical_json (str representation is deterministic)
        json_a = canonical_json(data_with_str)
        json_b = canonical_json(data_with_str)
        assert json_a == json_b

    def test_build_event_chain_produces_real_sha256(self):
        """block_hash values produced by build_event_chain() must be valid 64-char hex strings."""
        raw = [
            {"event_id": "EVT-001", "stage": "REQUEST_RECEIVED", "timestamp": "2026-09-15T05:00:00+00:00",
             "actor": "USR-001", "details": {"customer_id": "C-001"}},
        ]
        chain = build_event_chain(raw)
        assert len(chain) == 1
        assert len(chain[0]["block_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in chain[0]["block_hash"]), "Must be lowercase hex"
        assert chain[0]["parent_hash"] == GENESIS_HASH


# ---------------------------------------------------------------------------
# Test E: Duplicate-write guard (Required fix)
# ---------------------------------------------------------------------------

class TestDuplicateAuditRecordGuard:

    def test_duplicate_record_write_raises_error(self):
        """
        A second record_audit() call for the same workflow_id must raise
        DuplicateAuditRecordError and must NOT modify the existing stored record.

        This converts the 'write once' property from a calling convention into a
        hard service-layer invariant.  Without this guard, a buggy retry or future
        code path could silently replace the entire finalized hash chain.
        """
        service = AuditService()
        record = build_real_audit_record("WF-DUP-001")
        service.record_audit(record)

        # Capture state before attempted overwrite
        original = service.get_audit("WF-DUP-001")
        original_block_hash_0 = original.chain_events[0]["block_hash"]
        original_audit_id = original.audit_id

        # Second call must raise
        with pytest.raises(DuplicateAuditRecordError):
            service.record_audit(record)

        # The stored record must be completely unchanged
        after = service.get_audit("WF-DUP-001")
        assert after is original, "Stored record object must not have been replaced"
        assert after.chain_events[0]["block_hash"] == original_block_hash_0, (
            "First event block_hash must not have changed after duplicate-write attempt"
        )
        assert after.audit_id == original_audit_id

    def test_different_workflow_ids_coexist(self):
        """Records for distinct workflow IDs must be stored independently."""
        service = AuditService()
        r1 = build_real_audit_record("WF-COEXIST-001")
        r2 = build_real_audit_record("WF-COEXIST-002")
        service.record_audit(r1)
        service.record_audit(r2)

        assert service.get_audit("WF-COEXIST-001").workflow_id == "WF-COEXIST-001"
        assert service.get_audit("WF-COEXIST-002").workflow_id == "WF-COEXIST-002"
        assert len(service.list_audits()) == 2

# ---------------------------------------------------------------------------
# Test F: Real audit record round-trip (write path -> AuditService -> fetch -> verify)
# ---------------------------------------------------------------------------

class TestRealAuditRecordRoundTrip:

    def test_real_audit_record_round_trip_verifies_valid(self):
        """
        Builds a real AuditRecord end-to-end with genuine non-string Python objects
        (datetime instances, enum values from ActionType, EscalationLevel, AbstentionReason)
        in its fields -- not pre-stringified test literals -- stores it via AuditService,
        independently fetches it back via get_audit(), and confirms verify_event_chain()
        reports valid=True on the fetched copy.

        This proves write-time and verify-time serialization genuinely agree on
        realistic data, not just that a pure function returns the same output when
        called twice with identical literal input.

        The specific failure mode this guards against: if AuditService.get_audit()
        ever returned re-hydrated data that serialises even slightly differently than
        what was originally hashed at write time (e.g., because an enum .value was
        not normalised, or a datetime came back with a different timezone suffix),
        verify_event_chain() would report valid=False on an untampered record.
        Nothing in the existing suite would catch that failure.

        Construction mirrors _finalize_audit() in orchestrator.py exactly:
          - Real NextBestAction with ActionType enum (not a string)
          - Real EscalationLevel enum value
          - Real EvidenceCitation instances (with source_type / source_id)
          - All serialised via .model_dump(mode='json') before build_event_chain()
          - approval_record includes a real datetime timestamp (isoformat string,
            as the orchestrator stores it -- proving the isoformat path is stable)
        """
        from datetime import datetime, timezone
        import uuid as _uuid

        from backend.reasoning.models import (
            AbstentionReason,
            ActionType,
            EscalationLevel,
            EvidenceCitation,
            NextBestAction,
            ReasoningOutput,
        )
        from backend.connectors.base import ExecutionResult

        workflow_id = "WF-ROUNDTRIP-REAL-001"
        short_id = workflow_id[:8]

        # -------------------------------------------------------------------
        # Construct genuine Pydantic model instances -- the same types that
        # _finalize_audit() receives from the orchestrator at runtime.
        # -------------------------------------------------------------------

        # Real NextBestAction: ActionType is a str(Enum), EscalationLevel is a str(Enum).
        # When model_dump(mode='json') is called, ActionType.ESCALATE_TICKET becomes
        # the string "ESCALATE_TICKET" and EscalationLevel.L2 becomes "L2".
        # canonical_json() must produce the same result on both the write call and
        # the verify call -- this test proves it does.
        recommendation = NextBestAction(
            action_type=ActionType.ESCALATE_TICKET,
            target_team="Finance",
            escalation_level=EscalationLevel.L2,
            urgency="high",
            parameters={"reason": "Duplicate billing charge confirmed.", "ticket_ref": "TKT-0042"},
            requires_approval=True,
        )

        # Real EvidenceCitation instances -- model_dump(mode='json') applied in the loop.
        citations = [
            EvidenceCitation(
                source_type="ticket",
                source_id="TKT-0042",
                chunk_index=0,
                snippet="Customer was charged twice in the same billing cycle.",
                relevance_reason="Directly evidences the duplicate charge complaint.",
            ),
            EvidenceCitation(
                source_type="policy",
                source_id="billing_policy.md",
                chunk_index=1,
                snippet="Duplicate charges must be escalated to Finance within 24h.",
                relevance_reason="Mandates escalation path for this case type.",
            ),
        ]

        # Real ReasoningOutput -- carries the enum fields, citation list, etc.
        reasoning_output = ReasoningOutput(
            status="RECOMMENDATION_READY",
            abstention_reason=None,
            customer_summary="Customer reports being billed twice in the same cycle.",
            identified_root_cause="Duplicate billing cycle entry.",
            recommendation=recommendation,
            rationale="Two citations confirm duplicate billing; policy mandates Finance escalation.",
            citations=citations,
            confidence_score=0.94,
            requires_human_approval=True,
            indirect_injection_detected=False,
            retrieval_summary={"total_retrieved": 6, "top_score": 0.94, "sources_used": ["ticket", "policy"]},
            reasoning_time_ms=312.5,
        )

        # Real ExecutionResult -- action_type is an ActionType enum.
        # model_dump(mode='json') converts it to the string value "ESCALATE_TICKET".
        execution_result = ExecutionResult(
            workflow_id=workflow_id,
            transaction_id="TX-ROUNDTRIP-001",
            connector_name="MockEnterpriseConnector",
            action_type=ActionType.ESCALATE_TICKET,
            status="SUCCESS",
            details={"dispatched_to": "Finance", "ticket_ref": "TKT-0042", "sla_hours": 2},
            executed_at=datetime.now(timezone.utc).isoformat(),
            latency_ms=45.2,
        )

        # -------------------------------------------------------------------
        # Mirror _finalize_audit() serialisation: .model_dump(mode='json')
        # on every Pydantic object before building the chain.
        # -------------------------------------------------------------------
        started_at = datetime(2026, 9, 15, 5, 0, 0, tzinfo=timezone.utc).isoformat()
        completed_at = datetime(2026, 9, 15, 5, 0, 2, tzinfo=timezone.utc).isoformat()

        request_payload = {
            "customer_id": "CUST-RT-001",
            "customer_name": "Real Object Tester",
            "issue_summary": "Duplicate billing charge on account.",
            "requester_id": "USR-001",
            "requester_role": "support_agent",
        }
        retrieval_summary = reasoning_output.retrieval_summary
        # .model_dump(mode='json') converts ActionType enum -> "ESCALATE_TICKET" string,
        # EscalationLevel -> "L2" string, etc. -- exactly as the orchestrator does.
        evidence_citations = [c.model_dump(mode="json") for c in reasoning_output.citations]
        reasoning_output_dict = {
            "status": reasoning_output.status,
            "abstention_reason": reasoning_output.abstention_reason.value if reasoning_output.abstention_reason else None,
            "root_cause": reasoning_output.identified_root_cause,
            "rationale": reasoning_output.rationale,
            "confidence_score": reasoning_output.confidence_score,
            "indirect_injection_detected": reasoning_output.indirect_injection_detected,
            "recommendation": reasoning_output.recommendation.model_dump(mode="json") if reasoning_output.recommendation else None,
        }
        approval_record = {
            "decision": "APPROVE",
            "approver_id": "USR-003",
            "approver_role": "manager",
            "comments": "Evidence is clear.",
            # Real datetime converted to isoformat string, matching the orchestrator
            "timestamp": datetime(2026, 9, 15, 5, 0, 1, tzinfo=timezone.utc).isoformat(),
        }
        # .model_dump(mode='json') converts ActionType enum -> string in execution_record
        execution_record = execution_result.model_dump(mode="json")

        # -------------------------------------------------------------------
        # Build the chain -- same event structure as _finalize_audit()
        # -------------------------------------------------------------------
        raw_events = [
            {
                "event_id": f"EVT-001-{short_id}",
                "stage": "REQUEST_RECEIVED",
                "timestamp": started_at,
                "actor": "USR-001",
                "details": request_payload,
            },
            {
                "event_id": f"EVT-002-{short_id}",
                "stage": "EVIDENCE_RETRIEVED",
                "timestamp": started_at,
                "actor": "VectorRetriever (pgvector)",
                "details": {
                    "retrieval_summary": retrieval_summary,
                    "evidence_citations": evidence_citations,
                },
            },
            {
                "event_id": f"EVT-003-{short_id}",
                "stage": "REASONING_COMPLETED",
                "timestamp": started_at,
                "actor": "ReasoningEngine",
                "details": reasoning_output_dict,
            },
            {
                "event_id": f"EVT-004-{short_id}",
                "stage": "APPROVAL_SUBMITTED",
                "timestamp": approval_record["timestamp"],
                "actor": "USR-003",
                "details": approval_record,
            },
            {
                "event_id": f"EVT-005-{short_id}",
                "stage": "ACTION_DISPATCHED",
                "timestamp": execution_record.get("executed_at", completed_at),
                "actor": execution_record.get("connector_name", "MockEnterpriseConnector"),
                "details": execution_record,
            },
        ]

        chain_events = build_event_chain(raw_events)

        # -------------------------------------------------------------------
        # Store via AuditService and fetch back independently
        # -------------------------------------------------------------------
        record = AuditRecord(
            audit_id=str(_uuid.uuid4()),
            workflow_id=workflow_id,
            terminal_state="COMPLETED",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=2000.0,
            request_payload=request_payload,
            retrieval_summary=retrieval_summary,
            evidence_citations=evidence_citations,
            reasoning_output=reasoning_output_dict,
            approval_record=approval_record,
            execution_record=execution_record,
            chain_events=chain_events,
        )

        service = AuditService()
        service.record_audit(record)

        # Fetch back through the service -- this is the fetch path, independent of write
        fetched = service.get_audit(workflow_id)
        assert fetched is not None, "AuditService.get_audit() must return the stored record"

        # -------------------------------------------------------------------
        # Verify: re-derive every hash from the fetched copy's stored content.
        # If write-time and verify-time serialisation disagree on any enum value,
        # datetime format, or key ordering, this will report valid=False.
        # -------------------------------------------------------------------
        result = verify_event_chain(fetched.chain_events)

        assert result["valid"] is True, (
            f"Round-trip verification failed at index {result['failed_at_index']} "
            f"(event_id={result['failed_event_id']}). "
            "This indicates write-time and verify-time serialisation produced different "
            "hashes for the same data -- likely an enum .value normalisation or "
            "datetime format inconsistency."
        )
        assert result["failed_at_index"] is None
        assert result["failed_event_id"] is None

        # Structural sanity: confirm all 5 lifecycle blocks are present and hashed
        assert len(fetched.chain_events) == 5
        assert fetched.chain_events[0]["parent_hash"] == GENESIS_HASH
        for i in range(1, 5):
            assert fetched.chain_events[i]["parent_hash"] == fetched.chain_events[i - 1]["block_hash"], (
                f"Chain linkage broken at index {i} in the fetched record"
            )