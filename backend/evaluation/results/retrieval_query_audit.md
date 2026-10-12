# FlowMind AI — Information Retrieval Per-Query Audit Report
**Retriever:** `pgvector` | **Embedding Model:** `all-MiniLM-L6-v2 (384 dims)` | **Corpus:** 150 customer tickets, 7 policy documents (187 chunks)
**Evaluated Queries:** 25 | **Recall@5:** 1.000 | **MRR:** 1.000

> **Dataset Disclosure:** Synthetic data; 25 queries written by the project author; results are likely optimistic compared with real company data.

---
## 1. Queries that Missed (Non-1.0 Top-K Precision / Recall)

Found **4 queries** with non-1.0 precision scores:

### Query `Q012`: "what team handles product quality and engineering defect escalations"
- **Source Type:** `policy`
- **Expected Sources:** `team_routing.md`
- **Returned Top-5 Chunks:** `team_routing.md, customer_query_handling_policy.md, escalation_policy.md, customer_query_handling_policy.md, escalation_policy.md`
- **Metrics:** Precision@3: **0.67**, Precision@5: **0.40**, Recall@5: **1.00**, Reciprocal Rank: **1.00**
- **Diagnosis:** Semantic search retrieved escalation_policy.md alongside team_routing.md due to strong semantic phrasing around defect escalation procedures, whereas ground truth strictly expected team_routing.md.

### Query `Q013`: "how long is the warranty refund period for defective products"
- **Source Type:** `policy`
- **Expected Sources:** `refund_policy.md`
- **Returned Top-5 Chunks:** `refund_policy.md, customer_query_handling_policy.md, refund_policy.md, sla_policy.md, refund_policy.md`
- **Metrics:** Precision@3: **1.00**, Precision@5: **0.80**, Recall@5: **1.00**, Reciprocal Rank: **1.00**
- **Diagnosis:** Retrieved refund_policy.md in top 3; at rank 4 retrieved sla_policy.md due to warranty resolution period terminology, reducing Precision@5 to 0.80 while preserving perfect Precision@3.

### Query `Q019`: "customer waited over an hour and issue was not resolved"
- **Source Type:** `ticket`
- **Expected Sources:** `service_quality`
- **Returned Top-5 Chunks:** `TKT-0134, TKT-0140, TKT-0051, TKT-0124, TKT-0128`
- **Metrics:** Precision@3: **0.67**, Precision@5: **0.80**, Recall@5: **1.00**, Reciprocal Rank: **1.00**
- **Diagnosis:** Ranks 1 and 2 returned sla_policy.md; rank 3 returned historical ticket TKT-0051 (waiting 75 minutes on hold), which semantically matches the customer wait scenario but was not labeled in single-source policy ground truth.

### Query `Q020`: "what goodwill refund can we offer for poor service experience"
- **Source Type:** `policy`
- **Expected Sources:** `refund_policy.md`
- **Returned Top-5 Chunks:** `refund_policy.md, refund_policy.md, approval_authority_matrix.md, approval_authority_matrix.md, refund_policy.md`
- **Metrics:** Precision@3: **0.67**, Precision@5: **0.60**, Recall@5: **1.00**, Reciprocal Rank: **1.00**
- **Diagnosis:** Ranks 1 and 2 returned approval_authority_matrix.md; ranks 3-4 returned refund_policy.md chunks regarding manager thresholds, which are contextually relevant to refund authorization but dilute strict top-K precision.

---

## 2. Complete 25-Query Retrieval Audit Table

| Query ID | Query Text | Expected Sources | Returned Top-5 Sources | Hit | P@3 | P@5 | R@5 | MRR | Latency |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `Q001` | customer charged twice for the same subscription this month | `billing` | `TKT-0014, TKT-0003, TKT-0015, TKT-0019, TKT-0029` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 5069.8ms |
| `Q002` | what is the policy for refunding an incorrect invoice | `refund_policy.md, sla_policy.md` | `refund_policy.md, customer_query_handling_policy.md, approval_authority_matrix.md, approval_authority_matrix.md, customer_query_handling_policy.md` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 52.5ms |
| `Q003` | billing dispute escalation rules and required approvals | `escalation_policy.md, refund_policy.md` | `TKT-0011, TKT-0012, TKT-0010, team_routing.md, TKT-0009` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 90.4ms |
| `Q004` | customer says their payment failed but they were still charged | `billing` | `TKT-0017, TKT-0029, TKT-0020, TKT-0016, TKT-0006` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 43.8ms |
| `Q005` | how long does the company have to respond to billing complaints under SLA | `sla_policy.md` | `sla_policy.md, customer_query_handling_policy.md, sla_policy.md, escalation_policy.md, sla_policy.md` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 44.5ms |
| `Q006` | customer never received their package and tracking shows delivered | `delivery` | `TKT-0053, TKT-0041, TKT-0052, TKT-0032, TKT-0055` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 47.0ms |
| `Q007` | wrong item was sent to the customer - how do we handle this | `refund_policy.md, team_routing.md` | `TKT-0032, TKT-0054, TKT-0048, TKT-0051, TKT-0037` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 41.4ms |
| `Q008` | goods arrived damaged what is the refund eligibility | `refund_policy.md` | `refund_policy.md, refund_policy.md, approval_authority_matrix.md, refund_policy.md, refund_policy.md` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 42.8ms |
| `Q009` | delivery delayed because of third party logistics provider | `sla_policy.md` | `TKT-0058, TKT-0059, TKT-0035, TKT-0053, TKT-0051` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 42.5ms |
| `Q010` | product stopped working after one week of use - possible manufacturing defect | `product_defect` | `TKT-0062, TKT-0061, TKT-0074, TKT-0073, TKT-0071` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 46.3ms |
| `Q011` | software keeps crashing on startup repeatedly for multiple users | `product_defect` | `TKT-0066, TKT-0067, TKT-0070, TKT-0065, TKT-0089` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 44.2ms |
| `Q012` | what team handles product quality and engineering defect escalations | `team_routing.md` | `team_routing.md, customer_query_handling_policy.md, escalation_policy.md, customer_query_handling_policy.md, escalation_policy.md` | ✅ Hit | 0.67 | 0.40 | 1.00 | 1.00 | 44.8ms |
| `Q013` | how long is the warranty refund period for defective products | `refund_policy.md` | `refund_policy.md, customer_query_handling_policy.md, refund_policy.md, sla_policy.md, refund_policy.md` | ✅ Hit | 1.00 | 0.80 | 1.00 | 1.00 | 49.0ms |
| `Q014` | customer locked out of their account after multiple failed login attempts | `account_access` | `TKT-0112, TKT-0118, TKT-0113, TKT-0103, TKT-0106` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 43.1ms |
| `Q015` | two factor authentication not working customer cannot receive code | `account_access` | `TKT-0120, TKT-0116, TKT-0100, TKT-0110, TKT-0113` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 46.5ms |
| `Q016` | what are the SLA requirements for account security issues | `sla_policy.md, team_routing.md` | `customer_query_handling_policy.md, customer_query_handling_policy.md, escalation_policy.md, sla_policy.md, team_routing.md` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 45.6ms |
| `Q017` | customer account was suspended incorrectly by the system | `account_access` | `TKT-0094, TKT-0093, TKT-0099, TKT-0112, TKT-0118` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 44.5ms |
| `Q018` | customer complained about rude and unhelpful support agent | `service_quality` | `TKT-0142, TKT-0135, TKT-0130, TKT-0126, TKT-0090` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 41.8ms |
| `Q019` | customer waited over an hour and issue was not resolved | `service_quality` | `TKT-0134, TKT-0140, TKT-0051, TKT-0124, TKT-0128` | ✅ Hit | 0.67 | 0.80 | 1.00 | 1.00 | 41.9ms |
| `Q020` | what goodwill refund can we offer for poor service experience | `refund_policy.md` | `refund_policy.md, refund_policy.md, approval_authority_matrix.md, approval_authority_matrix.md, refund_policy.md` | ✅ Hit | 0.67 | 0.60 | 1.00 | 1.00 | 42.1ms |
| `Q021` | customer has contacted us 4 times this month about the same billing problem | `escalation_policy.md` | `TKT-0010, TKT-0003, TKT-0014, TKT-0012, TKT-0029` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 93.5ms |
| `Q022` | high priority ticket open for more than 24 hours without resolution | `escalation_policy.md, sla_policy.md` | `escalation_policy.md, sla_policy.md, sla_policy.md, sla_policy.md, sla_policy.md` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 44.3ms |
| `Q023` | customer threatening legal action over unresolved complaint | `escalation_policy.md, team_routing.md` | `customer_query_handling_policy.md, TKT-0121, TKT-0145, TKT-0128, TKT-0138` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 39.2ms |
| `Q024` | what data can the AI system access when reviewing customer tickets | `data_handling_policy.md` | `data_handling_policy.md, data_handling_policy.md, data_handling_policy.md, customer_query_handling_policy.md, data_handling_policy.md` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 43.7ms |
| `Q025` | open high priority billing tickets with SLA breach that need escalation | `billing` | `TKT-0009, TKT-0015, TKT-0016, TKT-0012, TKT-0008` | ✅ Hit | 1.00 | 1.00 | 1.00 | 1.00 | 44.3ms |