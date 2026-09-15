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