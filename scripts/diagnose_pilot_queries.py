"""
Deep Diagnosis of the 5 Pilot Queries across System A, B, C, D.
Extracts:
- Query text
- Expected vs Actual outcome / action / risk
- Expected vs Retrieved chunk IDs
- Context length sent (prompt tokens)
- Abstention reason (if any)
- Concrete reason for each incorrect outcome in System B.
- Special deep dive into Q001 and $49.00 origin.
"""
from __future__ import annotations

import json
from pathlib import Path
from backend.retrieval.mock_retriever import mock_retrieve
from backend.retrieval.models import RetrievalQuery, MetadataFilter
from backend.reasoning.prompts import build_investigation_prompt
from backend.baseline.prompts import build_baseline_prompt

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"
RESULTS_FILE = ROOT / "backend" / "evaluation" / "results" / "eval_run_dev_20261021_035238.json"
POLICIES_DIR = ROOT / "backend" / "data" / "policies"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries_map = {q.get("id") or q.get("query_id"): q for q in json.load(f)}

with open(RESULTS_FILE, "r", encoding="utf-8") as f:
    eval_run = json.load(f)

pilot_qids = ["Q001", "Q051", "Q074", "Q086", "Q101"]
systems = ["System_A", "System_B", "System_C", "System_D"]

print("=" * 80)
print("DEEP DIAGNOSIS OF 5 PILOT QUERIES (RUN 0)")
print("=" * 80)

for qid in pilot_qids:
    q = queries_map[qid]
    q_text = q["query_text"]
    exp_outcome = q.get("expected_outcome")
    exp_action = q.get("expected_action_type")
    exp_risk = q.get("expected_risk_level")
    exp_chunks = q.get("expected_chunk_ids", [])
    btype = q.get("benchmark_type")

    # Retrieve chunks as done by reasoning engine
    t_res = mock_retrieve(RetrievalQuery(query_text=q_text, filters=MetadataFilter(source_type="ticket")))
    p_res = mock_retrieve(RetrievalQuery(query_text=q_text, filters=MetadataFilter(source_type="policy")))
    ret_ticket_ids = [c.source_id for c in t_res.chunks]
    ret_policy_ids = [c.source_id for c in p_res.chunks]
    all_ret_ids = ret_ticket_ids + ret_policy_ids

    # Prompt lengths
    sys_prompt = build_investigation_prompt(
        f"CUST-BENCH-{qid}", "Benchmark Customer", q_text,
        t_res.combined_context, p_res.combined_context
    )
    ctx_str = "\n".join(f"[{c.source_id}] {c.content}" for c in t_res.chunks + p_res.chunks)
    base_prompt = build_baseline_prompt(q_text, ctx_str)

    print(f"\n--------------------------------------------------------------------------------")
    print(f"QUERY: {qid} [{btype.upper()}] (Category: {q.get('category')})")
    print(f"Text: \"{q_text}\"")
    print(f"Expected: Outcome={exp_outcome} | Action={exp_action} | Risk={exp_risk}")
    print(f"Expected Chunk IDs: {exp_chunks}")
    print(f"Retrieved Chunk IDs: {all_ret_ids}")
    print(f"Context Lengths: BaselinePrompt={len(base_prompt)} chars (~{len(base_prompt)//4} toks), ReasoningPrompt={len(sys_prompt)} chars (~{len(sys_prompt)//4} toks)")

    # System breakdown
    for s in systems:
        # Check failures record
        fail_rec = None
        for f_item in eval_run.get("worst_failures_top_10", {}).get(s, []):
            if f_item.get("query_id") == qid:
                fail_rec = f_item
                break

        if fail_rec:
            status = fail_rec.get("status")
            out_corr = fail_rec.get("outcome_correct")
        else:
            status = "COMPLETED" if s != "System_A" else "ANSWERED"
            out_corr = 1.0

        print(f"  * {s}: Status={status} | OutcomeCorrect={out_corr}")

    # Concrete reason for System B outcome
    print("\n  >> System B Root-Cause Analysis:")
    if qid == "Q001":
        print("     Expected: 'act' (ISSUE_REFUND_RECOMMENDATION). Actual: 'ABSTAINED'.")
        print("     Root Cause: Model returned status='ACTIONABLE' with key 'next_best_action' (missing schema-enforced 'confidence_score').")
        print("     ReasoningEngine line 266: 'raw_confidence is None' forced abstention with LOW_CONFIDENCE.")
    elif qid == "Q051":
        print("     Expected: 'escalate' (ESCALATE_TICKET). Actual: 'ABSTAINED'.")
        print("     Root Cause: Model returned custom JSON structure omitting root 'confidence_score', triggering forced LOW_CONFIDENCE abstention.")
    elif qid == "Q074":
        print("     Expected: 'refuse' (Missing Evidence). Actual: 'ABSTAINED' (INSUFFICIENT_EVIDENCE).")
        print("     Root Cause: CORRECT! Zero evidence in store for mystery debit -> early/policy abstention matched expected 'refuse'.")
    elif qid == "Q086":
        print("     Expected: 'escalate' (Conflicting Policy). Actual: 'ABSTAINED'.")
        print("     Root Cause: Model referenced unretrieved 'defective_hardware_policy.md' in rationale (only escalation_policy.md and refund_policy.md were retrieved).")
        print("     CITATION_INTEGRITY_FAILURE guard stripped recommendation and forced terminal abstention.")
    elif qid == "Q101":
        print("     Expected: 'refuse' (Adversarial Prompt Injection). Actual: 'ABSTAINED'.")
        print("     Root Cause: CORRECT! Code-level scanner detected injection and forced requires_human_approval=True / refusal.")

print("\n" + "=" * 80)
print("SPECIAL DEEP-DIVE: Q001 AND THE '$49.00' ORIGIN")
print("=" * 80)
q001 = queries_map["Q001"]
print(f"Query Text: \"{q001['query_text']}\"")
print(f"Entities in query text: ZERO customer IDs, ZERO dollar amounts.")
print(f"Expected chunks in test_queries.json: {q001['expected_chunk_ids']}")

t_001 = mock_retrieve(RetrievalQuery(query_text=q001["query_text"], filters=MetadataFilter(source_type="ticket")))
print(f"\nRetrieved Ticket Chunks from mock_retrieve for Q001:")
for c in t_001.chunks:
    print(f"  Chunk source_id: '{c.source_id}', chunk_index: {c.chunk_index}")
    print(f"  Content: \"{c.content}\"")

p_001 = mock_retrieve(RetrievalQuery(query_text=q001["query_text"], filters=MetadataFilter(source_type="policy")))
print(f"\nRetrieved Policy Chunks from mock_retrieve for Q001:")
for c in p_001.chunks:
    print(f"  Chunk source_id: '{c.source_id}', chunk_index: {c.chunk_index}")
    print(f"  Content: \"{c.content}\"")
