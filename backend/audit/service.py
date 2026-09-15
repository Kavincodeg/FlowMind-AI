"""
FlowMind AI - Audit Service (Phase 3)
In-memory and thread-safe audit log service with tamper-evident export capability.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from threading import Lock

from backend.audit.models import AuditRecord

logger = logging.getLogger(__name__)


class DuplicateAuditRecordError(Exception):
    """Raised when record_audit() is called for a workflow_id that already has a stored record.

    This enforces hash-chain immutability at the service layer: once a chain has been
    written for a given workflow_id it must never be overwritten or recomputed.
    If record_audit() could silently overwrite an existing record, a buggy retry or
    future code path could replace the entire finalized chain with a new one,
    destroying the tamper-evidence guarantee.
    """


class AuditService:
    """
    Centralized service for recording and retrieving audit trails.
    """

    def __init__(self):
        self._records: Dict[str, AuditRecord] = {}
        self._lock = Lock()

    def record_audit(self, record: AuditRecord) -> None:
        """Store an audit record.

        Raises:
            DuplicateAuditRecordError: If a record for the same workflow_id already
                exists.  This is a hard invariant: hash chains must be written once
                and never overwritten.
        """
        with self._lock:
            if record.workflow_id in self._records:
                raise DuplicateAuditRecordError(
                    f"Audit record for workflow '{record.workflow_id}' already exists "
                    f"and cannot be overwritten. Hash chain immutability must be preserved."
                )
            self._records[record.workflow_id] = record
        logger.info(
            "Audit record finalized: workflow=%s, terminal_state=%s, is_complete=%s, chain_length=%d",
            record.workflow_id,
            record.terminal_state,
            record.is_complete,
            len(record.chain_events),
        )

    def get_audit(self, workflow_id: str) -> Optional[AuditRecord]:
        """Retrieve audit record for a given workflow ID."""
        with self._lock:
            return self._records.get(workflow_id)

    def list_audits(self) -> List[AuditRecord]:
        """Retrieve all recorded audits."""
        with self._lock:
            return list(self._records.values())

    def export_audit_trail(self, workflow_id: str) -> Dict[str, Any]:
        """
        Export a structured, JSON-serializable audit trail.
        """
        record = self.get_audit(workflow_id)
        if not record:
            raise KeyError(f"Audit record not found for workflow ID: {workflow_id}")

        return {
            "audit_id": record.audit_id,
            "workflow_id": record.workflow_id,
            "terminal_state": record.terminal_state,
            "is_complete": record.is_complete,
            "timeline": {
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "duration_ms": record.duration_ms,
            },
            "investigation": {
                "request": record.request_payload,
                "retrieval": record.retrieval_summary,
                "citations": record.evidence_citations,
                "reasoning": record.reasoning_output,
            },
            "human_governance": record.approval_record,
            "automation_execution": record.execution_record,
            # Real SHA-256 hash chain events, written once at finalization.
            "chain_events": record.chain_events,
        }


# Global singleton instance
_audit_service = AuditService()


def get_audit_service() -> AuditService:
    """Dependency / accessor for the global audit service."""
    return _audit_service