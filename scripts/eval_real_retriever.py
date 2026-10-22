"""
Evaluate Real MiniLM Retriever over queries with expected_chunk_ids.
Uses sentence-transformers all-MiniLM-L6-v2 on real tickets and markdown policies.
"""
import json
from pathlib import Path
import numpy as np

from backend.retrieval.embedder import get_embedder
from backend.retrieval.ingestion import load_tickets, load_policies
from backend.evaluation.stats import compute_retrieval_metrics

# Load corpus
tickets_doc, ticket_chunks = load_tickets(Path("backend/data/synthetic/tickets.json"))
policies_doc, policy_chunks = load_policies(Path("backend/data/policies"))
all_chunks = ticket_chunks + policy_chunks

# Build chunk index map
chunk_ids = []
for c in all_chunks:
    s_id = c.metadata.get("source_id", "")
    idx = c.metadata.get("chunk_index", 0)
    chunk_ids.append((s_id, f"{s_id}#chunk_{idx}"))

print(f"Total chunks in corpus: {len(all_chunks)} ({len(ticket_chunks)} tickets, {len(policy_chunks)} policies)")

# Embed corpus
embedder = get_embedder()
corpus_texts = [c.content for c in all_chunks]
corpus_vecs = embedder.embed_texts(corpus_texts)

# Load test_queries.json
with open("backend/data/test_queries.json", encoding="utf-8") as f:
    queries = json.load(f)

# Alias map
def canonicalize(cid: str) -> str:
    # e.g., ticket_billing_chunk_0 -> TKT-0008, etc. if needed
    return cid

# Filter queries with non-empty expected_chunk_ids
dev_queries = [q for q in queries if q.get("split") == "dev" and q.get("expected_chunk_ids")]
print(f"Dev queries with expected chunks: {len(dev_queries)}")

by_type = {}
overall_metrics = []

for q in dev_queries:
    b_type = q.get("benchmark_type", "normal")
    expected = [canonicalize(e) for e in q.get("expected_chunk_ids", [])]
    q_vec = embedder.embed_texts([q["query_text"]])[0]
    
    # Cosine sim = dot product (normalized vectors)
    sims = np.dot(corpus_vecs, q_vec)
    ranked_indices = np.argsort(-sims)[:10]
    
    # Retrieved chunk IDs (source_ids and full ids)
    retrieved_cids = [chunk_ids[i][0] for i in ranked_indices]
    
    metrics = compute_retrieval_metrics(retrieved_cids, expected, k=5)
    overall_metrics.append(metrics)
    if b_type not in by_type:
        by_type[b_type] = []
    by_type[b_type].append(metrics)

print("\n=== REAL MINILM RETRIEVER EVALUATION (DEV QUERIES WITH EXPECTED CHUNKS) ===")
print(f"{'Query Type':<22} | {'Count':<5} | {'Recall@5':<10} | {'MRR':<10} | {'Precision@5':<12}")
print("-" * 68)

for b_type, mets in by_type.items():
    rec = np.mean([m["recall_at_k"] for m in mets])
    mrr = np.mean([m["reciprocal_rank"] for m in mets])
    prec = np.mean([m["precision_at_k"] for m in mets])
    print(f"{b_type:<22} | {len(mets):<5} | {rec:<10.4f} | {mrr:<10.4f} | {prec:<12.4f}")

all_rec = np.mean([m["recall_at_k"] for m in overall_metrics])
all_mrr = np.mean([m["reciprocal_rank"] for m in overall_metrics])
all_prec = np.mean([m["precision_at_k"] for m in overall_metrics])
print("-" * 68)
print(f"{'OVERALL':<22} | {len(overall_metrics):<5} | {all_rec:<10.4f} | {all_mrr:<10.4f} | {all_prec:<12.4f}")
