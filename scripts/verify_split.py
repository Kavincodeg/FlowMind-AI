import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries = json.load(f)

counts = defaultdict(lambda: defaultdict(int))
for q in queries:
    counts[q["benchmark_type"]][q["split"]] += 1

print(f"{len(queries)} total queries found in test_queries.json.")
print("| Benchmark Type       | Dev (60%)  | Test (40%) | Total    |")
print("|----------------------|------------|------------|----------|")
dev_tot, test_tot = 0, 0
for btype in ["normal", "multi_hop", "missing_evidence", "conflicting_policy", "adversarial"]:
    d = counts[btype]["dev"]
    t = counts[btype]["test"]
    dev_tot += d
    test_tot += t
    print(f"| {btype:<20} | {d:<10} | {t:<10} | {d+t:<8} |")
print("|======================|============|============|==========|")
print(f"| {'Total':<20} | {dev_tot:<10} | {test_tot:<10} | {dev_tot+test_tot:<8} |")

q1_25_splits = {q["id"]: q["split"] for q in queries if q["id"] in [f"Q{i:03d}" for i in range(1, 26)]}
assert len(q1_25_splits) == 25, f"Expected 25 legacy queries, found {len(q1_25_splits)}"
assert all(s == "dev" for s in q1_25_splits.values()), "Some Q001-Q025 are not in dev!"
print("Verified: All 25 legacy queries Q001-Q025 are strictly in dev.")
