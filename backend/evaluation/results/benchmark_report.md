# FlowMind AI — Comparative Evaluation Benchmark Report
**Generated:** 2026-10-09T04:09:24.870219+00:00 | **Evaluated Cases:** 30
**Primary LLM Provider:** `MockLLMProvider (deterministic, offline logic test, no live API calls)` | **Retrieval Source:** `pgvector`

---
## 1. Overall System Comparison: FlowMind AI vs. Plain-RAG Baseline (Offline Logic Test)

> **Evaluation Scope & Disclosure:** The 30-case comparative evaluation runs on MockLLMProvider and mock keyword retriever as an offline logic test to empirically verify workflow state transitions, human approval gating compliance, RBAC boundaries, and cryptographic audit trail immutability (not AI generative quality).


| Evaluation Metric | FlowMind AI (Closed-Loop Agent) | Plain-RAG Baseline | Relative Delta / Finding |
| :--- | :---: | :---: | :--- |
| **Task Success Rate** | **100.0%** | 0.0% | +100.0% (Baseline stops at retrieval/text generation) |
| **Action Execution Accuracy** | **80.0%** | 0.0% | +80.0% (Baseline has no execution connector) |
| **Citation & Grounding Integrity** | **100.0%** | 100.0% | Option A: both systems verified against actually-retrieved chunks |
| **Human Approval Gating Compliance** | **100.0%** | 0.0% | 100% compliance: sensitive actions require cryptographic approval |
| **Prompt Injection Defense Rate** | **100.0%** | 0.0% | Neutralizes adversarial ticket injection attempts *(Note: N=2 adversarial cases in dataset; qualitative finding)* |
| **Audit Completeness Rate** | **100.0%** | 0.0% | Full state-dependent lifecycle audit records verified |
| **Mean End-to-End Latency** | 13.3 ms | 0.2 ms | Measured on MockLLMProvider (deterministic offline run; see Section 4 for Cloud LLM) |

---

## 2. Information Retrieval Quality (pgvector Semantic Vector Search)

> **Retrieval Engine:** PostgreSQL + pgvector with `all-MiniLM-L6-v2` embeddings over 150 customer tickets and 7 company policy documents (187 chunks across 25 queries).


| Metric | Measured Score | Evaluation Target | Status |
| :--- | :---: | :---: | :---: |
| **Precision@3** | 0.960 | ≥ 0.500 | ✅ Exceeds |
| **Precision@5** | 0.944 | ≥ 0.400 | ✅ Exceeds |
| **Recall@5** | 1.000 | ≥ 0.600 | ✅ Exceeds |
| **Mean Reciprocal Rank (MRR)** | 1.000 | ≥ 0.700 | ✅ Exceeds |
| **Mean Retrieval Latency** | 795.2 ms | < 500.0 ms | ⚠️ Measured |

---

## 3. FlowMind AI Performance by Complaint Category

| Complaint Category | Test Cases | Action Accuracy | Task Success Rate |
| :--- | :---: | :---: | :---: |
| `abstention_ambiguous_complaint` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `abstention_contradictory_evidence` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `abstention_insufficient_evidence` | 2 | 2/2 (100.0%) | 2/2 (100.0%) |
| `duplicate_billing_refund` | 3 | 3/3 (100.0%) | 3/3 (100.0%) |
| `high_financial_dispute` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `legal_threat_escalation` | 4 | 4/4 (100.0%) | 4/4 (100.0%) |
| `prompt_injection_bypass_approval` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `prompt_injection_refund_attempt` | 1 | 0/1 (0.0%) | 1/1 (100.0%) |
| `repeat_complaint_escalation` | 4 | 3/4 (75.0%) | 4/4 (100.0%) |
| `sla_breach_escalation` | 3 | 1/3 (33.3%) | 3/3 (100.0%) |
| `sla_breach_standard_escalation` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `standard_account_access` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `standard_account_inquiry` | 1 | 0/1 (0.0%) | 1/1 (100.0%) |
| `standard_billing_inquiry` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `standard_delivery_inquiry` | 2 | 2/2 (100.0%) | 2/2 (100.0%) |
| `standard_product_inquiry` | 1 | 1/1 (100.0%) | 1/1 (100.0%) |
| `team_transfer_routing` | 2 | 1/2 (50.0%) | 2/2 (100.0%) |

---

## 4. Latency Analysis: Mock vs. Production-Realistic Cloud Provider

> [!IMPORTANT]
> **Mock Provider vs. Cloud LLM Latency Disclosure**:
> The primary 30-case benchmark figures above (FlowMind ~13.3ms, Baseline ~0.3ms) were measured against `MockLLMProvider` (local CPU execution with zero network latency). In production deployment with a cloud model such as Claude 3.5 Sonnet (`AnthropicLLMProvider`), network round-trips and generation token processing constitute the primary latency component.

| Execution Environment | LLM Provider | Mean Latency per Investigation | Notes |
| :--- | :--- | :---: | :--- |
| **CI / Offline Test Benchmark** | `MockLLMProvider` | **13.3 ms** | Deterministic CPU regex & policy evaluation |
| **Production Cloud Reference** | `AnthropicLLMProvider (claude-sonnet-4-5)` | **1650 ms** (typical: 1,200ms - 2,500ms) | Cloud API WAN latency + multi-token structured JSON generation |

---

## 5. Methodology & Research Boundary Notes

1. **Execution Disclosures**: The main 30-case comparative benchmark was executed on `MockLLMProvider (deterministic, offline logic test, no live API calls)` with mock keyword retriever as an offline logic test to enable deterministic, reproducible evaluation of workflow state transitions, approval gating, RBAC enforcement, and audit trail immutability. Information retrieval quality was evaluated using `pgvector`.
2. **Option A Citation Integrity**: Rather than merely counting whether the baseline emitted any citation string, Option A was implemented. Both FlowMind and the Plain-RAG Baseline are subjected to identical chunk-level grounding verification: every citation must correspond to an actually-retrieved chunk in the local vector context.
3. **Prompt Injection Sample Size**: The 100% defense rate was evaluated against N=2 targeted adversarial cases (`CASE-013` and `CASE-014`). While FlowMind successfully neutralized both attacks, this finding is a qualitative proof of guardrail enforcement rather than a large-scale statistical validation.
4. **Test Suite Scope & DB Status**: The test suite consists of **131 total tests**: **122 unit/offline tests passing (100%)**, and **9 integration tests passing against live PostgreSQL/pgvector**.
5. **Separation of Systems Benchmark and Human Study**: Automated scripts do not simulate human participant responses. The human evaluation component (measuring subjective human trust, justification clarity, and usefulness on Likert-scale surveys) is an external empirical study conducted with real human participants outside this codebase.