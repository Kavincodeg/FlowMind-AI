import json
from pathlib import Path

results_dir = Path("backend/evaluation/results")
files = sorted(results_dir.glob("eval_run_dev_*.json"))
latest = files[-1]
print(f"Reading latest run: {latest.name}")

with open(latest, "r", encoding="utf-8") as f:
    d = json.load(f)

print("\n=== FAILURE CLASSES BY SYSTEM ===")
print(json.dumps(d.get("failure_classes_by_system", {}), indent=2))

print("\n=== FAILURE CLASSES BY QUERY TYPE ===")
print(json.dumps(d.get("failure_classes_by_query_type", {}), indent=2))

print("\n=== SUMMARY METRICS ===")
for s, stats in d.get("summary_stats", {}).items():
    out_acc = stats.get('outcome_correct_mean')
    safe_rate = stats.get('safe_action_rate_mean')
    inj_def = stats.get('injection_defense_rate_mean')
    prec = stats.get('retrieval_precision_mean')
    rec = stats.get('retrieval_recall_mean')
    
    out_acc_str = f"{out_acc:.3f}" if out_acc is not None else "N/A"
    safe_rate_str = f"{safe_rate:.3f}" if safe_rate is not None else "N/A"
    inj_def_str = f"{inj_def:.3f}" if inj_def is not None else "N/A"
    prec_str = f"{prec:.3f}" if prec is not None else "N/A"
    rec_str = f"{rec:.3f}" if rec is not None else "N/A"
    
    print(f"{s:<10} | Outcome Acc: {out_acc_str:<6} | Safe Rate: {safe_rate_str:<6} | Inj Def: {inj_def_str:<6} | Prec@5: {prec_str:<6} | Rec@5: {rec_str:<6}")

print("\n=== PER-QUERY OUTCOME TABLE (12 QUERIES) ===")
print(f"{'QID':<6} | {'Type':<18} | {'System A':<10} | {'System B':<10} | {'System C':<10} | {'System D':<10} | {'B Fail Class':<12}")
print("-" * 85)

sys_runs = d.get("runs_raw", {})
for i in range(12):
    row_a = sys_runs.get("System_A", [])[i]
    row_b = sys_runs.get("System_B", [])[i]
    row_c = sys_runs.get("System_C", [])[i]
    row_d = sys_runs.get("System_D", [])[i]
    qid = row_b["query_id"]
    # Look up benchmark type from test_queries
    with open("backend/data/test_queries.json", "r", encoding="utf-8") as fq:
        all_q = json.load(fq)
    q_meta = next(q for q in all_q if (q.get("id") or q.get("query_id")) == qid)
    b_type = q_meta.get("benchmark_type")
    
    out_a = f"{row_a['outcome_correct']}"
    out_b = f"{row_b['outcome_correct']}"
    out_c = f"{row_c['outcome_correct']}"
    out_d = f"{row_d['outcome_correct']}"
    f_b = row_b.get("failure_class", "ok")
    print(f"{qid:<6} | {b_type:<18} | {out_a:<10} | {out_b:<10} | {out_c:<10} | {out_d:<10} | {f_b:<12}")

print("\n=== SYSTEM B ERROR DIAGNOSIS ===")
for i, row in enumerate(sys_runs.get("System_B", [])):
    if row.get("outcome_correct") != 1.0:
        qid = row["query_id"]
        print(f"\nQuery [{qid}]: status={row.get('status')}, outcome_correct={row.get('outcome_correct')}, failure_class={row.get('failure_class')}")
        print(f"  All retrieved chunks: {row.get('all_retrieved_chunks')}")
        print(f"  Cited chunks:         {row.get('cited_chunks')}")
        print(f"  Claims count:         {len(row.get('claims', []))}")
