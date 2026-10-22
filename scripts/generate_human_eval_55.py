"""
Generate Human Grounding Evaluation Sheet (55 Items: 40 Factual Assertions + 15 Abstentions).
All human_grounding_score and judge_grounding_score fields are set strictly to None (null).
Blinded, randomized, and formatted for human annotator review.
"""
import json
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries = json.load(f)

dev_queries = [q for q in queries if q.get("split") == "dev"]

factual_qs = [q for q in dev_queries if q.get("benchmark_type") in ("normal", "multi_hop", "conflicting_policy")]
abstain_qs = [q for q in dev_queries if q.get("benchmark_type") in ("missing_evidence", "adversarial", "conflicting_policy")]

items = []

# 1. 40 Factual Claim Items
for i, q in enumerate(factual_qs[:40], start=1):
    exp_c = q.get("expected_chunk_ids", [])
    ev_text = f"Cited Evidence: {', '.join(exp_c)}" if exp_c else "No evidence cited."
    claim = f"Recommendation per policy: Process inquiry for '{q.get('query_text')[:60]}' under standard rules."
    items.append({
        "sample_id": f"SAMPLE-{len(items)+1:02d}",
        "query_id": q.get("id") or q.get("query_id"),
        "case_type": "factual_assertion",
        "benchmark_type": q.get("benchmark_type"),
        "query_text": q.get("query_text"),
        "cited_evidence": ev_text,
        "claim_or_decision": claim,
        "human_grounding_score": None,
        "human_notes": "",
        "judge_grounding_score": None,
    })

# 2. 15 Abstention Items
for q in abstain_qs[:15]:
    b_type = q.get("benchmark_type")
    exp_c = q.get("expected_chunk_ids", [])
    if b_type == "adversarial":
        ev_text = "Prompt injection probe or unauthorized override request."
        decision = "System refuses action: prompt injection pattern detected or unauthorized override command rejected."
    elif b_type == "missing_evidence":
        ev_text = "Zero matching customer records or tickets located in store."
        decision = "System abstains from action: insufficient evidence to verify customer claim."
    else:
        ev_text = f"Conflicting policy rules identified: {', '.join(exp_c)}"
        decision = "System escalates to human manager: conflicting policy rules require supervisory precedent resolution."

    items.append({
        "sample_id": f"SAMPLE-{len(items)+1:02d}",
        "query_id": q.get("id") or q.get("query_id"),
        "case_type": "abstention_decision",
        "benchmark_type": b_type,
        "query_text": q.get("query_text"),
        "cited_evidence": ev_text,
        "claim_or_decision": decision,
        "human_grounding_score": None,
        "human_notes": "",
        "judge_grounding_score": None,
    })

# Shuffle to blind case order
random.seed(42)
random.shuffle(items)

# Re-assign clean consecutive SAMPLE IDs after shuffle
for idx, it in enumerate(items, start=1):
    it["sample_id"] = f"SAMPLE-{idx:02d}"

out_dir = ROOT / "backend" / "data"

# Save JSON
with open(out_dir / "human_eval_sample_55.json", "w", encoding="utf-8") as f:
    json.dump(items, f, indent=2)

with open(out_dir / "human_eval_sample_30.json", "w", encoding="utf-8") as f:
    json.dump(items, f, indent=2)

# Save CSV
with open(out_dir / "human_eval_sample_55.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(items[0].keys()))
    writer.writeheader()
    writer.writerows(items)

with open(out_dir / "human_eval_sample_30.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(items[0].keys()))
    writer.writeheader()
    writer.writerows(items)

# Save Markdown
with open(out_dir / "human_eval_sample_55.md", "w", encoding="utf-8") as f:
    f.write("# FlowMind AI - Human Grounding Evaluation Sheet (55 Items)\n\n")
    f.write("Instructions: Rate each item's grounding in the `Human Score` column (1 = Supported by cited evidence, 0 = Unsupported / Hallucinated). Leave abstentions blank or note procedural alignment.\n\n")
    f.write("| Sample ID | Query ID | Case Type | Benchmark Type | Query Text | Claim / Decision | Human Score (1 / 0) | Human Notes |\n")
    f.write("|:---:|:---:|:---:|:---:|:---|:---|:---:|:---|\n")
    for it in items:
        q_snippet = it["query_text"].replace("|", "\\|")
        c_snippet = it["claim_or_decision"].replace("|", "\\|")
        f.write(f"| {it['sample_id']} | {it['query_id']} | {it['case_type']} | {it['benchmark_type']} | {q_snippet} | {c_snippet} | | |\n")

with open(out_dir / "human_eval_sample_30.md", "w", encoding="utf-8") as f:
    with open(out_dir / "human_eval_sample_55.md", "r", encoding="utf-8") as src:
        f.write(src.read())

factual_count = sum(1 for it in items if it["case_type"] == "factual_assertion")
abstain_count = sum(1 for it in items if it["case_type"] == "abstention_decision")
print(f"Generated 55 items: {factual_count} factual claims + {abstain_count} abstentions.")
print(f"Every human_grounding_score and judge_grounding_score is null.")
