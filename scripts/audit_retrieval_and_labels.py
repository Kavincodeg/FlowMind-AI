"""
Audit Retrieval & Labels on DEV split.
Evaluates:
1. Retrieval metrics (Recall@k, MRR, Precision@k) overall and per query type using mock_retrieve.
2. Label-vs-Store Entity check: checks if entities in query text (customer IDs, amounts, ticket IDs, policy names)
   appear in the expected chunks.
3. Chunk ID nomenclature mismatch (e.g. ticket_billing_chunk_0 vs TKT-0008).
"""
import json
import re
from pathlib import Path
from backend.retrieval.mock_retriever import mock_retrieve
from backend.retrieval.models import RetrievalQuery, MetadataFilter
from backend.evaluation.stats import compute_retrieval_metrics

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"
POLICIES_DIR = ROOT / "backend" / "data" / "policies"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    all_queries = json.load(f)

dev_queries = [q for q in all_queries if q.get("split") == "dev"]
print(f"Total Dev Queries: {len(dev_queries)}")

# 1. Retrieval Metrics
metrics_by_type = {}
all_recalls = []
all_precisions = []
all_mrrs = []

for q in dev_queries:
    btype = q.get("benchmark_type", "normal")
    if btype not in metrics_by_type:
        metrics_by_type[btype] = {"recalls": [], "precisions": [], "mrrs": []}

    q_text = q["query_text"]
    exp_chunks = q.get("expected_chunk_ids", [])

    # Dual retrieve as done in ReasoningEngine
    t_res = mock_retrieve(RetrievalQuery(query_text=q_text, filters=MetadataFilter(source_type="ticket")))
    p_res = mock_retrieve(RetrievalQuery(query_text=q_text, filters=MetadataFilter(source_type="policy")))

    ret_chunks = [c.source_id for c in t_res.chunks] + [c.source_id for c in p_res.chunks]

    m = compute_retrieval_metrics(ret_chunks, exp_chunks)
    all_recalls.append(m["recall_at_k"])
    all_precisions.append(m["precision_at_k"])
    all_mrrs.append(m["reciprocal_rank"])

    metrics_by_type[btype]["recalls"].append(m["recall_at_k"])
    metrics_by_type[btype]["precisions"].append(m["precision_at_k"])
    metrics_by_type[btype]["mrrs"].append(m["reciprocal_rank"])

print("\n=== RETRIEVAL METRICS (OVERALL DEV SPLIT) ===")
print(f"Total Queries: {len(dev_queries)}")
print(f"Mean Recall@k:    {sum(all_recalls)/len(all_recalls):.4f}")
print(f"Mean Precision@k: {sum(all_precisions)/len(all_precisions):.4f}")
print(f"Mean MRR:         {sum(all_mrrs)/len(all_mrrs):.4f}")

print("\n=== RETRIEVAL METRICS BY BENCHMARK TYPE ===")
for btype, vals in metrics_by_type.items():
    n = len(vals["recalls"])
    mr = sum(vals["recalls"]) / n
    mp = sum(vals["precisions"]) / n
    mmrr = sum(vals["mrrs"]) / n
    print(f"[{btype}] (n={n}): Recall@k={mr:.4f}, Precision@k={mp:.4f}, MRR={mmrr:.4f}")

# 2. Entity Mismatch Check
print("\n=== LABEL VS STORE ENTITY CHECK ===")
mismatches = []
nomenclature_mismatches = []

for q in dev_queries:
    qid = q.get("id") or q.get("query_id")
    q_text = q["query_text"]
    exp_chunks = q.get("expected_chunk_ids", [])

    # Check for expected_chunk_ids style
    has_legacy_style = any(c.startswith("ticket_") and "chunk" in c for c in exp_chunks)
    if has_legacy_style:
        nomenclature_mismatches.append((qid, exp_chunks))

    # Extract entities from query text
    cust_ids = re.findall(r"cust-\d+", q_text, re.IGNORECASE)
    ticket_ids = re.findall(r"tkt-\d+", q_text, re.IGNORECASE)
    amounts = re.findall(r"\$\d+(?:,\d{3})*(?:\.\d{2})?", q_text)
    policies = [p.name for p in POLICIES_DIR.glob("*.md") if p.name.lower() in q_text.lower() or p.stem.replace("_", " ") in q_text.lower()]

    # Retrieve expected chunk text
    expected_texts = []
    for cid in exp_chunks:
        base = cid.split("#")[0]
        p_path = POLICIES_DIR / base
        if p_path.exists():
            expected_texts.append(p_path.read_text(encoding="utf-8"))

    combined_exp_text = " ".join(expected_texts).lower()

    # Check if entities in query appear in expected chunks
    query_entities = cust_ids + ticket_ids + amounts
    for ent in query_entities:
        if ent.lower() not in combined_exp_text:
            mismatches.append({
                "query_id": qid,
                "benchmark_type": q.get("benchmark_type"),
                "query_text": q_text,
                "missing_entity": ent,
                "expected_chunks": exp_chunks,
            })

print(f"Nomenclature Mismatches (e.g. ticket_billing_chunk_0): {len(nomenclature_mismatches)} / {len(dev_queries)}")
for qid, cids in nomenclature_mismatches[:5]:
    print(f"  {qid}: {cids}")

print(f"\nEntity Mismatches (entity in query absent from expected chunks): {len(mismatches)} instances")
for m in mismatches[:10]:
    print(f"  [{m['query_id']}] ({m['benchmark_type']}) entity '{m['missing_entity']}' absent from {m['expected_chunks']}")
    print(f"    Query: {m['query_text']}")
