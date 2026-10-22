"""
Generate 20-row blinded validation table for System A using real in-memory retriever.
Saves raw run file and exports blinded table for user labeling.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.retrieval.in_memory_retriever import in_memory_retrieve
from backend.retrieval.models import RetrievalQuery
from backend.reasoning.llm_provider import OllamaLLMProvider
from backend.evaluation.runner import map_baseline_free_text_to_outcome

DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"


with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries = json.load(f)

dev_queries = [q for q in queries if q.get("split") == "dev"]

# Pick 20 representative dev queries: 4 of each of the 5 benchmark types
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

print(f"Running System A generation for {len(sample_queries)} validation queries using in-memory retriever...")
provider = OllamaLLMProvider(model="llama3.1:8b", temperature=0.0)

run_records = []
blinded_rows = []

for idx, q in enumerate(sample_queries, start=1):
    qid = q.get("id") or q.get("query_id")
    q_text = q["query_text"]
    b_type = q.get("benchmark_type")
    exp_out = q.get("expected_outcome")
    exp_action = q.get("expected_action_type")
    
    print(f"[{idx}/20] Query {qid} ({b_type})...", flush=True)
    
    # Dual retrieval matching System A & B in runner
    rq_tickets = RetrievalQuery(query_text=q_text, top_k=5)
    rq_policies = RetrievalQuery(query_text=q_text, top_k=4)
    t_res = in_memory_retrieve(rq_tickets)
    p_res = in_memory_retrieve(rq_policies)
    shared_chunks = t_res.chunks + p_res.chunks
    
    context_lines = [
        f"[{c.source_id}#chunk_{c.chunk_index}]: {c.content}"
        for c in shared_chunks
    ]
    context_str = "\n\n".join(context_lines) if context_lines else "No relevant information found."
    
    allowed_chunk_ids = [f"{c.source_id}#chunk_{c.chunk_index}" for c in shared_chunks]
    allowed_str = ", ".join(f"[{cid}]" for cid in allowed_chunk_ids) if allowed_chunk_ids else "None"
    
    prompt = (
        f"Answer the customer question accurately based strictly on the provided evidence.\n"
        f"Cite all evidence using [source_id#chunk_index] (e.g. [TKT-0008#chunk_0], [refund_policy.md#chunk_0]).\n"
        f"ALLOWED CITATION ENUM: You may ONLY cite from the following retrieved chunk IDs: {allowed_str}.\n"
        f"Strictly do not cite any source ID not listed above.\n"
        f"If the evidence is insufficient to answer, state clearly that you cannot find sufficient information.\n"
        f"If an issue requires escalation per policies, state clearly that you are escalating the ticket.\n\n"
        f"Customer Query: {q_text}\n\n"
        f"Retrieved Evidence:\n{context_str}"
    )
    system_prompt = (
        "You are a helpful enterprise customer support assistant. Rely strictly on retrieved context. "
        "Always include citations in bracketed format [source_id#chunk_index]."
    )
    
    try:
        raw_ans = provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.0,
        )
    except Exception as exc:
        raw_ans = f"Error: {exc}"
        
    mapped = map_baseline_free_text_to_outcome(raw_ans)
    
    record = {
        "query_id": qid,
        "benchmark_type": b_type,
        "query_text": q_text,
        "expected_outcome": exp_out,
        "expected_action_type": exp_action,
        "mapper_decision": mapped,
        "raw_answer": raw_ans,
        "answer_first_400": raw_ans[:400].replace("\r", ""),
    }
    run_records.append(record)
    
    blinded_rows.append({
        "query_id": qid,
        "query_text": q_text,
        "answer_first_400": raw_ans[:400].replace("\r", "").replace("\n", " "),
    })

run_path = ROOT / "backend" / "evaluation" / "results" / "system_a_validation_run.json"
with open(run_path, "w", encoding="utf-8") as f:
    json.dump(run_records, f, indent=2)

print(f"Saved run records to {run_path}")
