# FlowMind AI

> Enterprise Workflow AI Agent — Final Year Engineering Project

## Phase 1: Retrieval Foundation (COMPLETE)

The knowledge backbone: ingest → chunk → embed → store → retrieve with citations.

---

## Quick Start

### 1. Prerequisites
- Docker Desktop installed and running
- Python 3.10+

### 2. Start the Database
```bash
docker-compose up -d
# Wait ~10s for pgvector to initialise
docker-compose ps   # should show "healthy"
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env if your DB settings differ from defaults
```

### 5. Ingest Data
```bash
# First run downloads ~90MB sentence-transformers model
python ingest_cli.py --source all
```

### 6. Run Tests
```bash
# Unit tests only (no DB required)
pytest backend/tests/test_retrieval.py -v -m "not integration"

# Full suite including integration (DB must be running + data ingested)
pytest backend/tests/test_retrieval.py -v

# With coverage
pytest backend/tests/test_retrieval.py -v --cov=backend/retrieval
```

---

## Project Structure

```
flowmind/
├── backend/
│   ├── retrieval/
│   │   ├── models.py       ← Pydantic data models
│   │   ├── ingestion.py    ← Load + chunk documents
│   │   ├── embedder.py     ← sentence-transformers embedder
│   │   ├── store.py        ← PostgreSQL + pgvector operations
│   │   └── retriever.py    ← Top-K search with citations
│   ├── db/
│   │   └── schema.sql      ← DB schema (auto-run by Docker)
│   ├── data/
│   │   ├── synthetic/
│   │   │   ├── tickets.json         ← 150 synthetic tickets
│   │   │   └── policies/            ← 5 policy markdown files
│   │   └── test_queries.json        ← 25 labelled retrieval queries
│   └── tests/
│       └── test_retrieval.py
├── ingest_cli.py            ← Ingestion entry point
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Architecture

```
RetrievalQuery (text + filters + top_k)
    ↓
Embedder.embed_query()        [all-MiniLM-L6-v2, 384 dims, local]
    ↓
store.ann_search()            [pgvector HNSW cosine + JSONB metadata filter]
    ↓
RetrievalResult               [ranked RetrievedChunk list with citations]
    ↓
result.combined_context       [formatted text block for LLM — Phase 2]
```

---

## Data

| Source | Count | Categories |
|---|---|---|
| Tickets | 150 | billing, delivery, product_defect, account_access, service_quality |
| Policies | 5 | escalation, SLA, team routing, refund, data handling |
| Test queries | 25 | mix of ticket, policy, and mixed queries with ground truth |

---

## Build Phases

| Phase | Status | Description |
|---|---|---|
| 1 — Retrieval | ✅ **Complete** | Ingest, chunk, embed, store, retrieve |
| 2 — Reasoning | ⏳ Pending | Evidence-grounded recommendation |
| 3 — RAG Baseline | ⏳ Pending | Comparison system (retrieve + answer only) |
| 4 — Orchestration | ⏳ Pending | Intent routing, workflow state |
| 5 — Approval UI + RBAC | ⏳ Pending | Human-in-the-loop, auth |
| 6 — Mock Connector + Audit | ⏳ Pending | Execution + full audit log |
| 7 — Evaluation Harness | ⏳ Pending | Metrics + benchmarks |
