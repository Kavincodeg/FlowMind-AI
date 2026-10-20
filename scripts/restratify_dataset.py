"""
Restratify FlowMind Benchmark Dataset (Phase 4).

Rules:
1. Primary stratification key: benchmark_type (normal, multi_hop, missing_evidence, conflicting_policy, adversarial).
2. All of Q001-Q025 MUST be placed in 'dev' (used in Phases 1-2).
3. Exactly 60% dev (72 cases) and 40% held-out test (48 cases).
   - normal: 30 dev (Q001-Q025 + 5 from Q026-Q050), 20 test (from Q026-Q050)
   - multi_hop: 12 dev, 8 test
   - missing_evidence: 9 dev, 6 test
   - conflicting_policy: 9 dev, 6 test
   - adversarial: 12 dev, 8 test
4. Secondary key: category where counts allow, stratified with seed=42.
5. Invariant check: refuse/escalate cases must have expected_action_type=None.
"""
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries = json.load(f)

# Sort by id
queries.sort(key=lambda x: x.get("id", x.get("query_id")))

rng = random.Random(42)

# Separate by benchmark_type
by_type = defaultdict(list)
for q in queries:
    # Guarantee refuse/escalate have None action
    if q.get("expected_outcome") in ("refuse", "escalate"):
        q["expected_action_type"] = None
    by_type[q["benchmark_type"]].append(q)

dev_ids = set()
test_ids = set()

# 1. Normal (50 items)
normal_items = by_type["normal"]
q1_25 = [q for q in normal_items if q["id"] in [f"Q{i:03d}" for i in range(1, 26)]]
q26_50 = [q for q in normal_items if q["id"] not in [f"Q{i:03d}" for i in range(1, 26)]]

assert len(q1_25) == 25, f"Expected 25 items in Q001-Q025, found {len(q1_25)}"
assert len(q26_50) == 25, f"Expected 25 items in Q026-Q050, found {len(q26_50)}"

# All Q001-Q025 go to dev
for q in q1_25:
    dev_ids.add(q["id"])

# 5 more from Q026-Q050 go to dev, remaining 20 go to test
# Stratify Q026-Q050 by category
q26_by_cat = defaultdict(list)
for q in q26_50:
    q26_by_cat[q["category"]].append(q)

q26_shuffled = list(q26_50)
rng.shuffle(q26_shuffled)
# Select 5 from different categories
selected_dev = []
used_cats = set()
for q in q26_shuffled:
    if q["category"] not in used_cats and len(selected_dev) < 5:
        selected_dev.append(q)
        used_cats.add(q["category"])

for q in q26_shuffled:
    if q not in selected_dev and len(selected_dev) < 5:
        selected_dev.append(q)

for q in selected_dev:
    dev_ids.add(q["id"])

for q in q26_50:
    if q["id"] not in dev_ids:
        test_ids.add(q["id"])

# Helper to stratify by category within a type
def stratify_group(items, target_dev_count):
    cat_map = defaultdict(list)
    for it in items:
        cat_map[it["category"]].append(it)
    
    group_dev = []
    group_test = []
    for cat, cat_items in sorted(cat_map.items()):
        shuffled = list(cat_items)
        rng.shuffle(shuffled)
        k = round(len(shuffled) * (target_dev_count / len(items)))
        group_dev.extend([x["id"] for x in shuffled[:k]])
        group_test.extend([x["id"] for x in shuffled[k:]])
    
    # Adjust to exact target
    diff = len(group_dev) - target_dev_count
    if diff > 0:
        for _ in range(diff):
            moved = group_dev.pop()
            group_test.append(moved)
    elif diff < 0:
        for _ in range(-diff):
            moved = group_test.pop()
            group_dev.append(moved)
            
    return set(group_dev), set(group_test)

# 2. Multi-hop (20 items): 12 dev, 8 test
mh_dev, mh_test = stratify_group(by_type["multi_hop"], 12)
dev_ids.update(mh_dev)
test_ids.update(mh_test)

# 3. Missing-evidence (15 items): 9 dev, 6 test
me_dev, me_test = stratify_group(by_type["missing_evidence"], 9)
dev_ids.update(me_dev)
test_ids.update(me_test)

# 4. Conflicting-policy (15 items): 9 dev, 6 test
cp_dev, cp_test = stratify_group(by_type["conflicting_policy"], 9)
dev_ids.update(cp_dev)
test_ids.update(cp_test)

# 5. Adversarial (20 items): 12 dev, 8 test
adv_dev, adv_test = stratify_group(by_type["adversarial"], 12)
dev_ids.update(adv_dev)
test_ids.update(adv_test)

assert len(dev_ids) == 72, f"Expected 72 dev, got {len(dev_ids)}"
assert len(test_ids) == 48, f"Expected 48 test, got {len(test_ids)}"
assert len(dev_ids & test_ids) == 0, "Overlap between dev and test!"

# Update query objects
for q in queries:
    q["split"] = "dev" if q["id"] in dev_ids else "test"

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(queries, f, indent=2, ensure_ascii=False)

print("Stratification complete with seed 42.")
print(f"Total dev: {len(dev_ids)} (60.0%), Total held-out test: {len(test_ids)} (40.0%)")
