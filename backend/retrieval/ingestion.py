"""
FlowMind AI - Ingestion & Chunking (Phase 1)

Loads source documents (tickets JSON, policy markdown files) and
splits them into Chunk objects ready for embedding.

Chunking strategies:
  - Tickets: sliding-window (256 tokens, 32-token overlap)
  - Policies: paragraph-aware (split on blank lines, merge short paras to ~200 tokens)

All token counts use a simple whitespace estimator (no tokenizer dependency needed;
exact tokenization is not required for chunking — only approximate sizing).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Tuple

from backend.retrieval.models import Chunk, Document, DocumentMetadata

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Token estimation (whitespace-based, ~4 chars/token approximation)
# ------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ------------------------------------------------------------------
# Sliding-window chunker (tickets)
# ------------------------------------------------------------------

def _sliding_window_chunks(
    text: str,
    source_meta: dict,
    window_tokens: int = 256,
    overlap_tokens: int = 32,
) -> List[Chunk]:
    """
    Split text into overlapping windows based on approximate token count.
    Used for short-form ticket text where structure is minimal.
    """
    words = text.split()
    window_words = window_tokens          # 1 word ~ 1 token approx
    overlap_words = overlap_tokens

    chunks: List[Chunk] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + window_words, len(words))
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            char_offset = len(" ".join(words[:start]))
            chunks.append(
                Chunk(
                    chunk_index=idx,
                    content=chunk_text,
                    token_count=_approx_tokens(chunk_text),
                    char_offset=char_offset,
                    metadata={**source_meta, "chunk_index": idx},
                )
            )
            idx += 1
        if end >= len(words):
            break
        start += window_words - overlap_words

    return chunks


# ------------------------------------------------------------------
# Paragraph chunker (policies)
# ------------------------------------------------------------------

def _paragraph_chunks(
    text: str,
    source_meta: dict,
    target_tokens: int = 200,
    min_tokens: int = 40,
) -> List[Chunk]:
    """
    Split markdown text on blank lines, then merge short paragraphs
    until each chunk is approximately target_tokens tokens.
    """
    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    merged: List[str] = []
    buffer = ""

    for para in raw_paragraphs:
        candidate = (buffer + "\n\n" + para).strip() if buffer else para
        if _approx_tokens(candidate) <= target_tokens:
            buffer = candidate
        else:
            if buffer:
                merged.append(buffer)
            # If this single paragraph is already large, keep it as-is
            buffer = para

    if buffer:
        merged.append(buffer)

    chunks: List[Chunk] = []
    char_offset = 0
    for idx, chunk_text in enumerate(merged):
        if _approx_tokens(chunk_text) < min_tokens and chunks:
            # Append tiny trailing chunks to the previous one
            chunks[-1] = Chunk(
                chunk_index=chunks[-1].chunk_index,
                content=chunks[-1].content + "\n\n" + chunk_text,
                token_count=_approx_tokens(chunks[-1].content + chunk_text),
                char_offset=chunks[-1].char_offset,
                metadata=chunks[-1].metadata,
            )
        else:
            chunks.append(
                Chunk(
                    chunk_index=idx,
                    content=chunk_text,
                    token_count=_approx_tokens(chunk_text),
                    char_offset=char_offset,
                    metadata={**source_meta, "chunk_index": idx},
                )
            )
        char_offset += len(chunk_text) + 2

    return chunks


# ------------------------------------------------------------------
# Ticket ingestion
# ------------------------------------------------------------------

def _ticket_to_text(ticket: dict) -> str:
    """Flatten a ticket dict into a single searchable text block."""
    history_text = ""
    if ticket.get("history"):
        history_lines = []
        for h in ticket["history"]:
            history_lines.append(
                f"  [{h.get('date', '')}] {h.get('agent', 'Agent')}: {h.get('note', '')}"
            )
        history_text = "Interaction History:\n" + "\n".join(history_lines)

    return (
        f"Ticket ID: {ticket['ticket_id']}\n"
        f"Customer: {ticket.get('customer_name', '')} (ID: {ticket.get('customer_id', '')})\n"
        f"Category: {ticket.get('issue_category', '')}\n"
        f"Priority: {ticket.get('priority', '')}\n"
        f"Status: {ticket.get('status', '')}\n"
        f"Assigned Team: {ticket.get('assigned_team', '')}\n"
        f"SLA Breach: {ticket.get('sla_breach', False)}\n"
        f"Created: {ticket.get('created_at', '')}\n"
        f"Issue Description:\n{ticket.get('issue_description', '')}\n"
        f"{history_text}"
    ).strip()


def load_tickets(tickets_path: Path) -> Tuple[List[Document], List[Chunk]]:
    """
    Load tickets from JSON file and split into chunks.

    Returns:
        (documents, chunks) — parallel lists (chunks reference their Document)
    """
    with open(tickets_path, encoding="utf-8") as f:
        tickets = json.load(f)

    documents: List[Document] = []
    all_chunks: List[Chunk] = []

    for ticket in tickets:
        source_id = ticket["ticket_id"]
        text = _ticket_to_text(ticket)

        meta = DocumentMetadata(
            source_type="ticket",
            source_id=source_id,
            customer_id=str(ticket.get("customer_id", "")),
            customer_name=ticket.get("customer_name", ""),
            issue_category=ticket.get("issue_category", ""),
            status=ticket.get("status", ""),
            assigned_team=ticket.get("assigned_team", ""),
            priority=ticket.get("priority", ""),
            sla_breach=bool(ticket.get("sla_breach", False)),
        )

        doc = Document(
            source_type="ticket",
            source_id=source_id,
            title=f"Ticket {source_id} — {ticket.get('issue_category', '')}",
            content=text,
            metadata=meta,
        )

        # Build chunk-level metadata (flat dict for pgvector JSONB)
        chunk_meta = {
            "source_type": "ticket",
            "source_id": source_id,
            "issue_category": ticket.get("issue_category", ""),
            "status": ticket.get("status", ""),
            "priority": ticket.get("priority", ""),
            "assigned_team": ticket.get("assigned_team", ""),
            "sla_breach": bool(ticket.get("sla_breach", False)),
            "customer_id": str(ticket.get("customer_id", "")),
        }

        chunks = _sliding_window_chunks(text, chunk_meta)
        documents.append(doc)
        all_chunks.extend(chunks)

    logger.info("Loaded %d tickets → %d chunks", len(documents), len(all_chunks))
    return documents, all_chunks


# ------------------------------------------------------------------
# Policy ingestion
# ------------------------------------------------------------------

def load_policies(policies_dir: Path) -> Tuple[List[Document], List[Chunk]]:
    """
    Load all .md files from policies_dir and split into chunks.

    Returns:
        (documents, chunks)
    """
    md_files = sorted(policies_dir.glob("*.md"))
    if not md_files:
        logger.warning("No .md policy files found in %s", policies_dir)
        return [], []

    documents: List[Document] = []
    all_chunks: List[Chunk] = []

    for md_file in md_files:
        filename = md_file.name
        text = md_file.read_text(encoding="utf-8")

        # Infer a human title from first H1
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else filename

        meta = DocumentMetadata(
            source_type="policy",
            source_id=filename,
            filename=filename,
            policy_category=filename.replace("_policy.md", "").replace("_", " "),
        )

        doc = Document(
            source_type="policy",
            source_id=filename,
            title=title,
            content=text,
            metadata=meta,
        )

        chunk_meta = {
            "source_type": "policy",
            "source_id": filename,
            "policy_category": meta.policy_category,
        }

        chunks = _paragraph_chunks(text, chunk_meta)
        documents.append(doc)
        all_chunks.extend(chunks)

    logger.info("Loaded %d policy files → %d chunks", len(documents), len(all_chunks))
    return documents, all_chunks
