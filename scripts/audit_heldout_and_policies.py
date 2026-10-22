import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"
POLICIES_DIR = ROOT / "backend" / "data" / "policies"
LOCK_FILE = ROOT / "backend" / "data" / "LABELS.lock"

queries = json.load(open(DATA_FILE, "r", encoding="utf-8"))
test_queries = [q for q in queries if q.get("split") in ("test", "held_out")]
dev_queries = [q for q in queries if q.get("split") == "dev"]

print("=== LABELS.LOCK CHECK ===")
print("Does LABELS.lock exist?:", LOCK_FILE.exists())
if LOCK_FILE.exists():
    print("LABELS.lock content:", LOCK_FILE.read_text(encoding="utf-8").strip())

print(f"\n=== HELD-OUT SPLIT AUDIT (n={len(test_queries)}) ===")
held_out_nom = []
for q in test_queries:
    exp = q.get("expected_chunk_ids", [])
    if any(c.startswith("ticket_") for c in exp):
        held_out_nom.append((q["id"], exp))
print("Held-out queries with ticket_* nomenclature:", len(held_out_nom))
for qid, exp in held_out_nom:
    print(f"  {qid}: {exp}")

# Entity mismatches in held-out
held_out_mismatches = []
for q in test_queries:
    qid = q["id"]
    q_text = q["query_text"]
    exp = q.get("expected_chunk_ids", [])
    amts = re.findall(r"\$\d+(?:,\d{3})*(?:\.\d{2})?", q_text)
    exp_text = " ".join([(POLICIES_DIR / c.split("#")[0]).read_text(encoding="utf-8") for c in exp if (POLICIES_DIR / c.split("#")[0]).exists()]).lower()
    for a in amts:
        if a.lower() not in exp_text:
            held_out_mismatches.append((qid, q.get("benchmark_type"), a, exp))
print("Held-out entity mismatches:", len(held_out_mismatches))
for m in held_out_mismatches:
    print(f"  [{m[0]}] ({m[1]}) entity '{m[2]}' not in {m[3]}")

print("\n=== CONFLICTING-POLICY QUERIES AUDIT ===")
all_cp = [q for q in queries if q.get("benchmark_type") == "conflicting_policy"]
print(f"Total Conflicting Policy queries: {len(all_cp)}")
available_policies = {p.name for p in POLICIES_DIR.glob("*.md")}
print("Available policies in corpus:", sorted(list(available_policies)))

for q in all_cp:
    qid = q["id"]
    split = q.get("split")
    q_text = q["query_text"]
    exp = q.get("expected_chunk_ids", [])
    
    # Check if policies mentioned in text or expected chunks exist
    missing_expected = [c for c in exp if c.split("#")[0] not in available_policies]
    
    # Look for policy names mentioned in query text
    text_policies_mentioned = re.findall(r"[a-z0-9_]+_policy\.md|[a-z0-9_]+_matrix\.md", q_text.lower())
    text_phrases_mentioned = re.findall(r"([a-z ]+policy)", q_text.lower())
    
    print(f"\n[{qid}] ({split})")
    print(f"   Query: \"{q_text}\"")
    print(f"   Expected Chunks: {exp}")
    if missing_expected:
        print(f"   --> MISSING FROM CORPUS: {missing_expected}")

print("\n=== Q086 SPECIFIC AUDIT ===")
q086 = next(q for q in queries if q.get("id") == "Q086")
print(f"Q086 Query: \"{q086['query_text']}\"")
print(f"Q086 Expected Chunks: {q086.get('expected_chunk_ids')}")
print(f"Q086 Notes: \"{q086.get('notes')}\"")
print(f"Q086 Benchmark Type: {q086.get('benchmark_type')}")
print(f"Q086 Expected Action: {q086.get('expected_action_type')}")
print(f"Q086 Expected Outcome: {q086.get('expected_outcome')}")
