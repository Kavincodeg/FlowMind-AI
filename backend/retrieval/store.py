"""
FlowMind AI - Vector Store (Phase 1)

Handles all PostgreSQL + pgvector interactions:
  - Upsert documents
  - Batch insert chunks with embeddings
  - Delete documents (cascades to chunks)
  - Fetch chunk by ID (for citation resolution)
  - Raw ANN search (called by retriever.py)
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator, List, Optional
from uuid import UUID

import numpy as np
import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection
from pgvector.psycopg2 import register_vector

from backend.retrieval.models import Chunk, Document, RetrievedChunk

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Connection helpers
# ------------------------------------------------------------------

def _get_dsn() -> str:
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'flowmind')} "
        f"user={os.getenv('PGUSER', 'flowmind')} "
        f"password={os.getenv('PGPASSWORD', 'flowmind_dev')}"
    )


@contextmanager
def _conn() -> Generator[PgConnection, None, None]:
    """Context manager: open connection, register pgvector, auto-commit/rollback."""
    conn = psycopg2.connect(_get_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    register_vector(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ------------------------------------------------------------------
# Document operations
# ------------------------------------------------------------------

def upsert_document(doc: Document) -> UUID:
    """
    Insert or update a document record.
    Returns the doc_id (UUID).
    """
    sql = """
        INSERT INTO documents (source_type, source_id, title, metadata)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (source_type, source_id)
        DO UPDATE SET
            title      = EXCLUDED.title,
            metadata   = EXCLUDED.metadata,
            created_at = NOW()
        RETURNING doc_id
    """
    meta_json = psycopg2.extras.Json(doc.metadata.model_dump(mode="json", exclude_none=True))
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (doc.source_type, doc.source_id, doc.title, meta_json))
            row = cur.fetchone()
    doc_id = UUID(str(row["doc_id"]))
    logger.debug("Upserted document %s -> %s", doc.source_id, doc_id)
    return doc_id


def delete_document(source_type: str, source_id: str) -> int:
    """Delete a document and all its chunks. Returns rows deleted."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM documents WHERE source_type=%s AND source_id=%s",
                (source_type, source_id),
            )
            return cur.rowcount


# ------------------------------------------------------------------
# Chunk operations
# ------------------------------------------------------------------

def upsert_chunks(chunks: List[Chunk]) -> None:
    """
    Batch-insert chunks.  On conflict (doc_id, chunk_index) update embedding + content.
    Each chunk MUST have doc_id and embedding set before calling this.
    """
    if not chunks:
        return

    sql = """
        INSERT INTO chunks
            (doc_id, chunk_index, content, token_count, char_offset, embedding, metadata)
        VALUES %s
        ON CONFLICT (doc_id, chunk_index)
        DO UPDATE SET
            content     = EXCLUDED.content,
            token_count = EXCLUDED.token_count,
            embedding   = EXCLUDED.embedding,
            metadata    = EXCLUDED.metadata
    """

    records = []
    for c in chunks:
        if c.doc_id is None or c.embedding is None:
            raise ValueError(f"Chunk {c.chunk_index} missing doc_id or embedding")
        records.append((
            str(c.doc_id),
            c.chunk_index,
            c.content,
            c.token_count,
            c.char_offset,
            np.array(c.embedding, dtype=np.float32),
            psycopg2.extras.Json(c.metadata),
        ))

    with _conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, records, page_size=200)

    logger.debug("Upserted %d chunks", len(chunks))


def get_chunk_by_id(chunk_id: UUID) -> Optional[dict]:
    """Fetch a single chunk row by primary key (for citation resolution)."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM chunks WHERE chunk_id = %s",
                (str(chunk_id),),
            )
            row = cur.fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------------
# ANN search (used by retriever.py)
# ------------------------------------------------------------------

def ann_search(
    query_vector: np.ndarray,
    top_k: int,
    metadata_filter: Optional[dict] = None,
    score_threshold: float = 0.30,
) -> List[RetrievedChunk]:
    """
    Perform cosine-similarity ANN search against the chunks table.

    Args:
        query_vector:    shape (384,), already normalised
        top_k:           number of results to return
        metadata_filter: JSONB containment filter dict (e.g. {"source_type": "ticket"})
        score_threshold: minimum cosine similarity (0-1)

    Returns:
        List of RetrievedChunk sorted by score descending.
    """
    params: list = [query_vector, top_k * 4]   # over-fetch then threshold-filter
    where_clauses = []

    if metadata_filter:
        where_clauses.append("c.metadata @> %s")
        params.append(psycopg2.extras.Json(metadata_filter))

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
        SELECT
            c.chunk_id,
            c.doc_id,
            c.chunk_index,
            c.content,
            c.metadata,
            1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c
        {where_sql}
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """
    # query_vector appears twice: once for score calc, once for ORDER BY
    final_params = [query_vector] + params[1:]   # metadata filter already in params
    # rebuild cleanly
    base_params: list = [query_vector]
    if metadata_filter:
        base_params.append(psycopg2.extras.Json(metadata_filter))
    base_params += [query_vector, top_k * 4]

    where_sql_2 = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql2 = f"""
        SELECT
            c.chunk_id,
            c.doc_id,
            c.chunk_index,
            c.content,
            c.metadata,
            1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c
        {where_sql_2}
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql2, base_params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        score = float(row["score"])
        if score < score_threshold:
            continue
        meta = dict(row["metadata"])
        results.append(
            RetrievedChunk(
                chunk_id=UUID(str(row["chunk_id"])),
                doc_id=UUID(str(row["doc_id"])),
                source_type=meta.get("source_type", ""),
                source_id=meta.get("source_id", ""),
                chunk_index=row["chunk_index"],
                content=row["content"],
                score=score,
                metadata=meta,
            )
        )
        if len(results) >= top_k:
            break

    return results
