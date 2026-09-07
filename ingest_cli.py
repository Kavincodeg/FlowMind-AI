#!/usr/bin/env python3
"""
FlowMind AI - Ingestion CLI (Phase 1)

Usage:
    python ingest_cli.py --source all
    python ingest_cli.py --source tickets
    python ingest_cli.py --source policies
    python ingest_cli.py --source all --clear

Ingestion pipeline:
  1. Load documents from JSON / markdown files
  2. Split into chunks
  3. Embed chunks (sentence-transformers, local)
  4. Upsert into PostgreSQL + pgvector
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

# Load .env before importing modules that read env vars
load_dotenv(Path(__file__).parent / ".env")

from backend.retrieval.embedder import Embedder
from backend.retrieval.ingestion import load_policies, load_tickets
from backend.retrieval.store import delete_document, upsert_chunks, upsert_document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_cli")

DATA_DIR = Path(__file__).parent / "backend" / "data" / "synthetic"
TICKETS_FILE = DATA_DIR / "tickets.json"
POLICIES_DIR = DATA_DIR / "policies"


def ingest_tickets(embedder: Embedder, clear: bool = False) -> None:
    logger.info("=== Ingesting Tickets ===")
    documents, chunks = load_tickets(TICKETS_FILE)

    if clear:
        logger.info("Clearing existing ticket documents...")
        cleared = 0
        for doc in tqdm(documents, desc="Clearing"):
            cleared += delete_document("ticket", doc.source_id)
        logger.info("Cleared %d document rows", cleared)

    logger.info("Upserting %d documents...", len(documents))
    doc_id_map: dict = {}
    for doc in tqdm(documents, desc="Upserting docs"):
        doc_id = upsert_document(doc)
        doc_id_map[doc.source_id] = doc_id

    # Assign doc_ids to chunks and match by source_id in metadata
    for chunk in chunks:
        src_id = chunk.metadata.get("source_id")
        if src_id and src_id in doc_id_map:
            chunk.doc_id = doc_id_map[src_id]

    logger.info("Embedding %d chunks...", len(chunks))
    t0 = time.perf_counter()
    embedder.embed_chunks(chunks)
    embed_time = time.perf_counter() - t0
    logger.info("Embedding took %.2fs (%.0f chunks/s)", embed_time, len(chunks) / embed_time)

    logger.info("Upserting %d chunks into pgvector...", len(chunks))
    t1 = time.perf_counter()
    # Insert in batches of 500
    batch_size = 500
    for i in tqdm(range(0, len(chunks), batch_size), desc="Inserting chunks"):
        upsert_chunks(chunks[i : i + batch_size])
    insert_time = time.perf_counter() - t1
    logger.info("Insert took %.2fs", insert_time)
    logger.info("Ticket ingestion complete: %d docs, %d chunks", len(documents), len(chunks))


def ingest_policies(embedder: Embedder, clear: bool = False) -> None:
    logger.info("=== Ingesting Policies ===")
    documents, chunks = load_policies(POLICIES_DIR)

    if clear:
        logger.info("Clearing existing policy documents...")
        for doc in tqdm(documents, desc="Clearing"):
            delete_document("policy", doc.source_id)

    logger.info("Upserting %d policy documents...", len(documents))
    doc_id_map: dict = {}
    for doc in tqdm(documents, desc="Upserting docs"):
        doc_id = upsert_document(doc)
        doc_id_map[doc.source_id] = doc_id

    for chunk in chunks:
        src_id = chunk.metadata.get("source_id")
        if src_id and src_id in doc_id_map:
            chunk.doc_id = doc_id_map[src_id]

    logger.info("Embedding %d chunks...", len(chunks))
    embedder.embed_chunks(chunks)

    logger.info("Upserting chunks into pgvector...")
    upsert_chunks(chunks)
    logger.info("Policy ingestion complete: %d docs, %d chunks", len(documents), len(chunks))


def main() -> None:
    parser = argparse.ArgumentParser(description="FlowMind AI — Document Ingestion CLI")
    parser.add_argument(
        "--source",
        choices=["tickets", "policies", "all"],
        required=True,
        help="Which data source to ingest",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing documents for the source before re-ingesting",
    )
    args = parser.parse_args()

    logger.info("Loading embedding model (first run will download ~90MB)...")
    embedder = Embedder()

    if args.source in ("tickets", "all"):
        ingest_tickets(embedder, clear=args.clear)

    if args.source in ("policies", "all"):
        ingest_policies(embedder, clear=args.clear)

    logger.info("All done!")


if __name__ == "__main__":
    main()
