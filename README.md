# FlowMind AI

> Evidence-Grounded Enterprise Governance & Workflow AI Agent  
> Final Year Engineering Project

FlowMind AI investigates customer complaints, retrieves grounded evidence from past tickets and enterprise policies, performs structured multi-step reasoning, enforces strict Role-Based Access Control (RBAC) and human approval gates, dispatches actions through enterprise connectors, and maintains a genuine SHA-256 tamper-evident audit hash chain.

---

## System Architecture & Implemented Phases

```
Complaint Investigation Request
          ↓
[Phase 1] Knowledge Retrieval Backbone (pgvector + all-MiniLM-L6-v2)
          ↓ (Ranked chunks + policy excerpts with citations)
[Phase 2] Evidence-Grounded Reasoning Engine vs Plain-RAG Baseline
          ↓ (Hallucination stripping, injection scan, next-best-action recommendation)
[Phase 3] Orchestration, Human Governance & Cryptographic Audit Trail
          ├─ Auto-Execution (Low-risk routine actions, e.g., Tier 1 refunds < $30)
          ├─ Human Approval Gate (RBAC enforced: Support Agent, Team Lead, Manager, Admin)
          ├─ Enterprise Connectors (Mock connector dispatch with transaction tracking)
          └─ Tamper-Evident SHA-256 Hash Chain (Written once, immutable audit store)
          ↓
[Phase 4] Empirical Evaluation Harness (FlowMind AI vs Plain-RAG comparison)
          ↓
[Frontend] Interactive Enterprise Console (Vite + React + TypeScript)
```

### Phase 1: Retrieval Foundation
The knowledge backbone indexes customer support history and enterprise policies:
- **Ingestion & Chunking**: Sliding-window chunker with metadata preservation for 150 historical support tickets across 5 categories; paragraph-based chunker for 5 structured enterprise policies.
- **Embedding**: Local `all-MiniLM-L6-v2` sentence-transformer generating 384-dimensional normalized vector embeddings.
- **Vector Store**: PostgreSQL 16 with the `pgvector` extension utilizing HNSW cosine index and JSONB metadata filters.
- **Retrieval Engine**: Top-$K$ semantic similarity search with score thresholding, structured citations, and context assembly.

### Phase 2: Evidence-Grounded Reasoning & Plain-RAG Baseline
Structured reasoning with strict safety guardrails:
- **Reasoning Engine**: Produces `ReasoningOutput` containing customer summary, identified root cause, confidence score, and `NextBestAction`.
- **Citation Integrity Verification**: Automated guardrail that verifies every cited chunk ID against retrieved context; hallucinated citations are stripped. If reasoning depends on ungrounded claims or confidence falls below threshold, the agent enters formal abstention.
- **Adversarial Injection Defense**: Code-level and prompt-level detection scanner rejecting prompt injection and privilege-escalation payloads.
- **Plain-RAG Baseline**: Unconstrained comparator implementing standard RAG without hallucination verification, injection screening, or abstention logic for empirical ablation.

### Phase 3: Orchestration, Governance, Connectors & Audit
Closed-loop workflow execution and governance:
- **State Machine Orchestrator**: Manages workflow instances across explicit states (`RECEIVED` → `RETRIEVING` → `REASONING` → `PENDING_APPROVAL` / `AUTO_EXECUTED` → `APPROVED_EXECUTED` / `REJECTED` / `ABSTAINED` / `FAILED`).
- **Role-Based Access Control (RBAC)**: Enforces permission boundaries across four personas (`support_agent`, `team_lead`, `manager`, `admin`). Resolves user identities strictly server-side from bearer tokens to prevent client header forgery. Unauthorized modifications or approvals raise `RBACPermissionDeniedError`.
- **Human Approval Gate**: Reviewers can approve, reject (with mandatory rationale), or modify action parameters prior to dispatch.
- **Connectors**: Dispatches approved actions to external systems with transaction IDs and latency measurements.
- **Audit Service**: Write-once audit persistence guarded by `DuplicateAuditRecordError` preventing overwriting or re-computation.

### Phase 4: Comparative Empirical Evaluation
Automated benchmark and evaluation harness:
- **13 Benchmark Scenarios**: Covers standard billing escalations, defect routing, goodwill refunds, missing evidence cases, and adversarial injection attacks.
- **Comparative Metrics**: Evaluates FlowMind AI against Plain-RAG on Task Success Rate (100% vs 38.5%), Citation Grounding Integrity (100% vs 61.5%), Hallucination Rate (0.0% vs 38.5%), and Injection Defense Rate (100% vs 0.0%).
- **Structural Invariants**: Automated tests verifying that no sensitive action executes without approval, no abstention executes, and every terminal workflow produces a valid audit record.

---

## Cryptographic SHA-256 Audit Hash Chain

FlowMind AI implements a genuine cryptographic audit chain (`backend/audit/chain.py`) for complete tamper detection across all workflow lifecycle events:

1. **Deterministic Canonical Serialization**:
   Event payloads are serialized using strict key sorting, whitespace compaction, and UTF-8 encoding:
   ```python
   canonical_json(data) = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
   ```
2. **Block-Linked SHA-256 Hashing**:
   Each event hash binds its canonical content to the preceding block's hash:
   ```
   block_hash[0] = SHA-256(canonical_json(event[0]) + "::" + GENESIS_HASH)
   block_hash[i] = SHA-256(canonical_json(event[i]) + "::" + block_hash[i-1])
   ```
   The genesis block uses a fixed 64-character hex zero sentinel.
3. **Independent Server-Side Verification Endpoint**:
   The endpoint `GET /api/workflow/{id}/audit/verify` independently re-derives every block hash from scratch from the raw event content stored in the database. It validates:
   - **Content Integrity**: Recomputed hash matches stored `block_hash`.
   - **Chain Linkage**: Stored `parent_hash` matches previous block's `block_hash`.
   If tampering occurs, it returns `valid: false` along with the exact `failed_at_index` and `failed_event_id`.
4. **Scope & Threat Model Limitation**:
   > **Note on Security Guarantees**: This hash chain guarantees **tamper evidence** against accidental data corruption, unauthorized field modifications, event omission, and out-of-order alterations. Like Git commit hashes, it does **not** prevent an attacker with full root/database write access from recalculating an entire chain forward from the point of alteration. Durability against malicious database administrators would require anchoring block hashes to an external, write-once ledger or append-only transparency log.

---

## Project Structure

```
FlowMind-AI/
├── backend/
│   ├── api/                  ← FastAPI application, dependencies & REST routes
│   │   ├── main.py           ← App factory, CORS, exception handlers
│   │   └── routes.py         ← Investigation, approval, audit & benchmark endpoints
│   ├── audit/                ← Tamper-evident cryptographic audit system
│   │   ├── chain.py          ← SHA-256 hashing, chain builder & verification
│   │   ├── models.py         ← AuditRecord and AuditEvent schema
│   │   └── service.py        ← AuditService with DuplicateAuditRecordError guard
│   ├── baseline/             ← Unconstrained Plain-RAG comparator
│   │   └── plain_rag.py      ← Standard RAG implementation without guardrails
│   ├── connectors/           ← Enterprise action execution layer
│   │   ├── base.py           ← Connector interface & execution results
│   │   └── mock_connector.py ← Mock enterprise connector with latency simulation
│   ├── data/                 ← Ground-truth datasets & test collections
│   │   ├── synthetic/
│   │   │   ├── tickets.json  ← 150 support tickets across 5 categories
│   │   │   └── policies/     ← 5 enterprise markdown policy documents
│   │   └── test_queries.json ← 25 retrieval benchmark queries
│   ├── db/
│   │   └── schema.sql        ← PostgreSQL schema (documents, chunks, audit_log)
│   ├── evaluation/           ← Empirical evaluation & invariant verification
│   │   ├── benchmark_cases.py← 13 evaluation test cases
│   │   ├── comparative.py    ← FlowMind AI vs Plain-RAG benchmark runner
│   │   └── reporter.py       ← Markdown & JSON evaluation report generators
│   ├── orchestrator/         ← Workflow execution state machine
│   │   └── orchestrator.py   ← Lifecycle orchestrator & audit finalizer
│   ├── reasoning/            ← Evidence-grounded reasoning & guardrails
│   │   ├── engine.py         ← Multi-step reasoning pipeline & citation check
│   │   ├── llm_provider.py   ← MockLLMProvider & Anthropic provider factory
│   │   ├── models.py         ← Pydantic models for reasoning, actions & citations
│   │   └── prompts.py        ← Grounded prompt templates & injection scanner
│   ├── retrieval/            ← Vector search & knowledge backbone
│   │   ├── embedder.py       ← sentence-transformers local embedder
│   │   ├── ingestion.py      ← Ticket & policy document chunkers
│   │   ├── models.py         ← Chunk, Document & RetrievedChunk models
│   │   ├── retriever.py      ← Top-K vector search with metadata filters
│   │   └── store.py          ← PostgreSQL + pgvector interface
│   ├── security/             ← Identity & access control
│   │   └── rbac.py           ← Role definitions, permission matrix & tokens
│   └── tests/                ← Comprehensive test suite
│       ├── test_audit_chain.py  ← SHA-256 chain, linkage & tamper tests
│       ├── test_baseline.py     ← Plain-RAG baseline behavior tests
│       ├── test_evaluation.py   ← Benchmark metrics & structural invariants
│       ├── test_orchestration.py← State transitions & connector execution
│       ├── test_rbac.py         ← Role permissions & token resolution tests
│       ├── test_reasoning.py    ← Reasoning engine & injection defense tests
│       └── test_retrieval.py    ← Unit & PostgreSQL integration tests
├── frontend/                 ← React 18 + TypeScript web console
│   ├── src/
│   │   ├── components/       ← UI components
│   │   │   ├── ApprovalGate.tsx         ← Human governance & decision UI
│   │   │   ├── AuditExplorer.tsx        ← Cryptographic hash chain inspector
│   │   │   ├── BenchmarkDashboard.tsx   ← Table 1 comparative benchmark view
│   │   │   ├── EvidenceDrawer.tsx       ← Grounded citation view with snippets
│   │   │   ├── ExecutionOutcome.tsx     ← Connector execution status card
│   │   │   ├── Header.tsx               ← Persona switcher & status bar
│   │   │   └── InvestigationConsole.tsx ← Scenario selection & input form
│   │   ├── api.ts            ← Axios client & API integrations
│   │   ├── types.ts          ← Shared frontend TypeScript definitions
│   │   └── index.css         ← Theme, design tokens & responsive layout
│   ├── screenshots/          ← End-to-end verification screenshot captures
│   ├── tests/
│   │   └── flowmind.spec.ts  ← 14 Playwright end-to-end browser tests
│   ├── vite.config.ts        ← Vite dev server & backend API proxy
│   └── package.json
├── docker-compose.yml        ← PostgreSQL 16 + pgvector container definition
├── ingest_cli.py             ← CLI to ingest & embed tickets and policies
├── pytest.ini                ← Pytest configuration with integration marker
└── requirements.txt          ← Python backend dependencies
```

---

## Setup & Getting Started

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- Docker Desktop or Docker engine with WSL2 (for pgvector database)

### 2. Backend & Database Setup
```bash
# 1. Start PostgreSQL with pgvector
docker-compose up -d

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Ingest knowledge documents into pgvector
python ingest_cli.py --source all

# 5. Start the FastAPI backend server
python -m uvicorn backend.api.main:app --port 8000
```
Backend API will be available at `http://127.0.0.1:8000` (Swagger docs at `http://127.0.0.1:8000/docs`).

### 3. Frontend Setup
The frontend communicates with the backend via Vite's built-in development proxy (forwarding `/api` requests to `http://127.0.0.1:8000`).

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
Open `http://localhost:5173/` in your browser.

---

## Test Execution & Verification

The project enforces clean separation between fast, isolated unit tests, live-database integration tests, and browser end-to-end tests:

### 1. Backend Unit Tests (No Database Required)
Unit tests mock the storage boundary and test all reasoning logic, RBAC rules, state transitions, baseline comparisons, and SHA-256 hash-chain algorithms in isolation:
```bash
# Run all backend unit tests (default behavior; integration tests deselected)
pytest backend/tests/ -v
```

### 2. Backend Integration Tests (Live PostgreSQL + pgvector Required)
Integration tests require a running Docker container and populated database to test real vector embeddings, HNSW ANN searches, metadata filters, and retrieval latency:
```bash
# Ensure database is running and populated
docker-compose up -d
python ingest_cli.py --source all

# Run integration tests explicitly
pytest -m integration -v
```

### 3. Frontend End-to-End Tests (Playwright)
Browser tests validate the full interactive user experience, RBAC persona switching, approval gating, and live audit hash-chain verification in Chromium:
```bash
cd frontend
npx playwright test
```

---

## Verified Test Coverage Summary

All tests are verified and passing:

| Test Layer | Test Command | Passed | Failed | Description |
|---|---|:---:|:---:|---|
| **Backend Unit Tests** | `pytest backend/tests/ -v` | **110** | 0 | Pure-logic tests covering reasoning, guardrails, RBAC matrix, orchestrator, baseline, evaluation invariants, and 15 SHA-256 audit chain determinism/tamper tests |
| **Backend Integration Tests** | `pytest -m integration -v` | **9** | 0 | Real pgvector vector search, HNSW retrieval, score thresholding, precision/recall, and latency against live PostgreSQL |
| **Frontend Playwright E2E** | `npx playwright test` | **14** | 0 | Full browser tests: scenarios, persona switching, human approval, rejection rationale, injection defense, and cryptographic hash chain inspection |
| **Total Verified Tests** | | **133** | **0** | **Complete green suite across all system layers** |
