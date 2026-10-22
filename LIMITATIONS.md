# System Limitations & Engineering Disclosures

## Evaluation Harness Retrieval Architecture
> **Important Disclosure**: **eval uses in-memory MiniLM retrieval, not pgvector/HNSW**.

1. **Retrieval Engine in Comparative Evaluation**:
   - The comparative evaluation runner (`backend/evaluation/runner.py`) uses `InMemoryRetriever` backed by local `all-MiniLM-L6-v2` dense sentence embeddings (384 dimensions, normalized) and exact cosine similarity over the full 187-chunk corpus (150 historical customer tickets + 37 policy chunks).
   - In deployment and Phase 1 integration tests, FlowMind AI supports PostgreSQL 16 with the `pgvector` extension and HNSW indexing (`store.py`). However, for reproducible offline evaluation and standalone execution on host environments without Docker or active PostgreSQL daemons, the evaluation benchmark runs using the in-memory MiniLM retriever rather than requiring pgvector/HNSW.
   - Metadata filters (`source_type`, `issue_category`, `priority`, `status`, `assigned_team`, `sla_breach`) in the in-memory retriever strictly replicate the SQL JSONB containment logic from Phase 1.

2. **System Guardrails During Benchmark**:
   - Evaluation runs are strictly blocked if `DEMO_MODE=true` (must run with `demo_mode OFF`).
   - Evaluation runs are strictly blocked if any mock or keyword stub retriever is detected.

3. **Grounding & Traceability**:
   - The Reasoning Engine strictly verifies refund amounts against extracted customer request amounts and cited chunks (`AMOUNT_NOT_VERIFIED`).
   - Ungrounded claims without verified citations trigger automatic abstention (`CITATION_INTEGRITY_FAILURE` / `INSUFFICIENT_EVIDENCE`).
