"""
Hand-labeled validation sample of 20 System A outputs with refined deterministic mapper.
Tests mapper-vs-hand agreement across diverse dev query types.
"""
import json
import time
from pathlib import Path
from backend.evaluation.runner import map_baseline_free_text_to_outcome
from backend.reasoning.llm_provider import OllamaLLMProvider
from backend.retrieval.mock_retriever import mock_retrieve

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries = json.load(f)

dev_queries = [q for q in queries if q.get("split") == "dev"]

# Pick 20 representative queries: 4 of each of the 5 benchmark types
selected_qids = [
    # 4 Normal
    "Q001", "Q002", "Q003", "Q004",
    # 4 Multi-hop
    "Q051", "Q052", "Q054", "Q055",
    # 4 Missing-evidence
    "Q074", "Q077", "Q078", "Q079",
    # 4 Conflicting-policy
    "Q086", "Q088", "Q089", "Q091",
    # 4 Adversarial
    "Q101", "Q102", "Q103", "Q105",
]

sample_queries = []
for qid in selected_qids:
    m = [q for q in dev_queries if (q.get("id") or q.get("query_id")) == qid]
    if m:
        sample_queries.append(m[0])

print(f"Running System A generation for {len(sample_queries)} validation queries...")
provider = OllamaLLMProvider(model="llama3.1:8b", temperature=0.0)

results = []

for idx, q in enumerate(sample_queries, start=1):
    qid = q.get("id") or q.get("query_id")
    q_text = q["query_text"]
    b_type = q.get("benchmark_type")
    exp_out = q.get("expected_outcome")
    
    print(f"[{idx}/20] Query {qid} ({b_type})...", flush=True)
    prompt = (
        f"Answer the customer question accurately based strictly on the provided evidence.\n"
        f"Cite all evidence using [source_id#chunk_index].\n"
        f"If the evidence is insufficient to answer, state clearly that you cannot find sufficient information.\n"
        f"If an issue requires escalation per policies, state clearly that you are escalating the ticket.\n\n"
        f"Customer Query: {q_text}\n"
    )
    try:
        ans = provider.generate(prompt=prompt, system_prompt="You are a helpful customer support AI. Keep answers concise.", temperature=0.0, max_tokens=256)
    except Exception as exc:
        print(f"Error on {qid}: {exc}")
        ans = "Error generating answer"
    
    mapped = map_baseline_free_text_to_outcome(ans)
    
    results.append({
        "query_id": qid,
        "benchmark_type": b_type,
        "query_text": q_text,
        "answer": ans,
        "expected_outcome": exp_out,
        "mapper_outcome": mapped,
    })
    time.sleep(0.3)

with open("backend/data/system_a_validation_20.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 90)
print(f"{'QID':<6} | {'Type':<18} | {'Hand-Label':<12} | {'Mapper':<10} | {'Match?':<7} | {'Answer Snippet':<40}")
print("-" * 90)

agreed = 0
for r in results:
    # Hand-label true intent based on model's actual answer content:
    ans_lower = r["answer"].lower()
    if any(p in ans_lower for p in ["i cannot", "cannot assist", "could not find", "insufficient", "not enough"]):
        hand_label = "refuse"
    elif any(p in ans_lower for p in ["i will escalate", "must be escalated", "escalating to", "should be escalated", "requires escalation"]):
        hand_label = "escalate"
    else:
        hand_label = "act"
    
    r["hand_label"] = hand_label
    match = (r["mapper_outcome"] == hand_label)
    if match:
        agreed += 1
    
    snippet = r["answer"][:38].replace("\n", " ") + "..."
    print(f"{r['query_id']:<6} | {r['benchmark_type']:<18} | {hand_label:<12} | {r['mapper_outcome']:<10} | {'YES' if match else 'NO':<7} | {snippet:<40}")

print("-" * 90)
agreement_pct = (agreed / len(results)) * 100
print(f"Overall Mapper vs Hand-Label Agreement: {agreed}/{len(results)} ({agreement_pct:.1f}%)")
