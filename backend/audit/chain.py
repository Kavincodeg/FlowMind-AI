"""
FlowMind AI - SHA-256 Tamper-Evident Audit Hash Chain (Phase 3 amendment)

This module provides all hash-chain primitives used at both write time (_finalize_audit)
and verification time (GET /api/workflow/{id}/audit/verify).  Keeping these functions in a
single, import-only module ensures that the verifier recomputes hashes through exactly the
same code-path as the writer - no divergence is possible.

SCOPE NOTE
----------
This hash chain detects accidental or partial data tampering - e.g. a field edited in
storage without recomputing the downstream chain.  It does NOT protect against an attacker
who has the same system access as the hashing code (read/write access to the event store),
because no HMAC secret or asymmetric signature is used.  Anyone who can both edit stored
event content AND recompute matching hashes could forge a valid-looking chain.  This is the
same limitation Git commit hashes have, and is a deliberate, well-understood trade-off for
an internal audit log of this scope.

Storage note
------------
AuditRecord objects are currently held in-memory (a Python dict protected by a threading.Lock
inside AuditService).  No persistent database is used (Phase 3).  The hash chain's
tamper-evidence is a structural property of the chain itself and is independent of the storage
backend - a persistent DB would improve durability but would not change the chain's integrity
guarantees.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Genesis sentinel
# ---------------------------------------------------------------------------

GENESIS_HASH: str = "0" * 64
"""64 hex zeros used as the parent_hash of the first event in every workflow chain.
This value is fixed and must never change - both the write path and the verify path
depend on it being identical."""


# ---------------------------------------------------------------------------
# Canonical serialisation
# ---------------------------------------------------------------------------

def canonical_json(data: Any) -> str:
    """Return a deterministic, byte-stable JSON string suitable for hashing.

    Rules applied:
    - Keys are sorted alphabetically at every level of nesting (sort_keys=True).
    - No extra whitespace (separators=(',', ':')) to prevent accidental padding.
    - ASCII-safe output (ensure_ascii=True) eliminates UTF-8 encoding ambiguity.
    - Non-JSON-native Python types (datetime, UUID, Enum, Decimal, etc.)
      are coerced to their str() representation via default=str.

    IMPORTANT: callers must pre-convert any Pydantic models to plain dicts using
    .model_dump(mode='json') *before* passing them here, so that the 'details'
    dict already contains only JSON-native types (str, int, float, bool, None, list,
    dict).  This guarantees that write-time and verify-time serialisation produce
    bit-for-bit identical output.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


# ---------------------------------------------------------------------------
# Single-event hashing
# ---------------------------------------------------------------------------

_CONTENT_KEYS = ("event_id", "stage", "timestamp", "actor", "details")
# The ordered set of event fields that contribute to the hash.
# block_hash and parent_hash are intentionally excluded - they are
# derived outputs, not content inputs.


def _extract_content(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the content fields from an event dict."""
    return {k: event[k] for k in _CONTENT_KEYS if k in event}


def compute_event_hash(content_fields: Dict[str, Any], previous_hash: str) -> str:
    """Compute SHA-256(canonical_json(content_fields) + '::' + previous_hash).

    The '::' separator prevents length-extension ambiguity between the JSON
    payload and the hex hash string.

    Args:
        content_fields: Dict containing only the content fields to hash (not
            block_hash or parent_hash).
        previous_hash: The block_hash of the immediately preceding event,
            or GENESIS_HASH for the first event.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    raw = canonical_json(content_fields) + "::" + previous_hash
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Chain construction (write path)
# ---------------------------------------------------------------------------

def build_event_chain(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach block_hash and parent_hash to each event in sequence.

    Takes a list of raw event dicts (each containing event_id, stage,
    timestamp, actor, details) and returns a new list of dicts with
    two additional fields populated:

    - parent_hash: the block_hash of the previous event, or
      GENESIS_HASH for the first event.
    - block_hash: SHA-256 derived from the event's content fields and
      parent_hash.

    The input dicts are not mutated; new dicts are returned.

    Args:
        raw_events: Ordered list of lifecycle event dicts.  'details' values
            must already be JSON-native (use .model_dump(mode='json') on any
            Pydantic models before passing here).

    Returns:
        A new list of event dicts, each augmented with block_hash and
        parent_hash.
    """
    chained: List[Dict[str, Any]] = []
    prev_hash = GENESIS_HASH

    for event in raw_events:
        content = _extract_content(event)
        block_hash = compute_event_hash(content, prev_hash)

        chained.append({
            **event,
            "parent_hash": prev_hash,
            "block_hash": block_hash,
        })
        prev_hash = block_hash

    return chained


# ---------------------------------------------------------------------------
# Chain verification (verify path - fully independent of the write path)
# ---------------------------------------------------------------------------

def verify_event_chain(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-derive every event hash from scratch and confirm chain integrity.

    Performs two independent checks per event:

    (a) Content integrity - recompute block_hash from the event's stored
        content fields and parent_hash; compare to the stored block_hash.
    (b) Chain linkage - compare the stored parent_hash to the stored
        block_hash of the immediately preceding event (or GENESIS_HASH
        for the first event).

    Both checks are required.  Check (b) independently of (a) is critical: an
    attacker who edits content *and* updates block_hash in-place but forgets
    to propagate the change to the next event's parent_hash will be caught by
    (b) even if (a) would pass (because (a) re-derives using the stored,
    now-wrong parent_hash).

    Args:
        events: Ordered list of event dicts, each bearing event_id,
            stage, timestamp, actor, details, block_hash, and parent_hash.

    Returns:
        Dict with keys:
            - valid (bool): True if all events pass both checks.
            - failed_at_index (int | None): 0-based index of the first
              failing event; None if valid.
            - failed_event_id (str | None): event_id of the failing
              event; None if valid.
    """
    if not events:
        return {"valid": True, "failed_at_index": None, "failed_event_id": None}

    expected_parent = GENESIS_HASH

    for idx, event in enumerate(events):
        stored_block_hash: str = event.get("block_hash", "")
        stored_parent_hash: str = event.get("parent_hash", "")

        # (b) Chain linkage check - does stored parent_hash match what we expect?
        if stored_parent_hash != expected_parent:
            logger.warning(
                "verify_event_chain: linkage failure at index %d (event_id=%s): "
                "stored parent_hash=%s expected=%s",
                idx, event.get("event_id"), stored_parent_hash, expected_parent,
            )
            return {
                "valid": False,
                "failed_at_index": idx,
                "failed_event_id": event.get("event_id"),
            }

        # (a) Content integrity check - recompute block_hash from content + parent
        content = _extract_content(event)
        recomputed = compute_event_hash(content, stored_parent_hash)

        if recomputed != stored_block_hash:
            logger.warning(
                "verify_event_chain: content integrity failure at index %d (event_id=%s): "
                "stored block_hash=%s recomputed=%s",
                idx, event.get("event_id"), stored_block_hash, recomputed,
            )
            return {
                "valid": False,
                "failed_at_index": idx,
                "failed_event_id": event.get("event_id"),
            }

        expected_parent = stored_block_hash

    return {"valid": True, "failed_at_index": None, "failed_event_id": None}