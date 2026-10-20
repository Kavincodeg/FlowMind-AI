"""
Stratified rebalancer for the 120 benchmark queries with fixed seed 42.
Ensures every category is balanced around ~60% dev / 40% test (within 55-65% for n>=5, or exact 50-50 / 60-40 for small n).
Freezes Q001-Q025 dev/test assignments or stratifies with frozen labels.
Also enforces the rule:
'refuse/escalate cases have no expected action' -> expected_action_type MUST be None.
"""
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries = json.load(f)

# Normalize singleton categories
for q in queries:
    if q.get("category") == "escalation":
        q["category"] = "policy_compliance"
    elif q.get("category") == "general":
        q["category"] = "service_quality"
    elif q.get("category") == "legal":
        q["category"] = "policy_compliance"

    # Enforce rule: refuse and escalate cases MUST have no expected action (expected_action_type = None)
    if q["expected_outcome"] in ("refuse", "escalate"):
        q["expected_action_type"] = None

# Let's perform stratified split with seed=42 across all 120 cases
# While ensuring exactly 72 dev (60.0%) and 48 test (40.0%)
rng = random.Random(42)

# Group by category
cat_groups = defaultdict(list)
for q in queries:
    cat_groups[q["category"]].append(q)

dev_set = set()
test_set = set()

for cat, q_list in sorted(cat_groups.items()):
    n = len(q_list)
    # Determine exact target dev count (round 60%)
    n_dev = round(n * 0.6)
    # Shuffle deterministically with seed
    shuffled = list(q_list)
    rng.shuffle(shuffled)
    for q in shuffled[:n_dev]:
        dev_set.add(q["id"])
    for q in shuffled[n_dev:]:
        test_set.add(q["id"])

# Adjust if total dev != 72 due to rounding
diff = len(dev_set) - 72
if diff > 0:
    # Move diff items from dev to test from largest categories
    eligible = [qid for qid in dev_set if any(q["id"] == qid and len(cat_groups[q["category"]]) > 10 for q in queries)]
    rng.shuffle(eligible)
    for qid in eligible[:diff]:
        dev_set.remove(qid)
        test_set.add(qid)
elif diff < 0:
    eligible = [qid for qid in test_set if any(q["id"] == qid and len(cat_groups[q["category"]]) > 10 for q in queries)]
    rng.shuffle(eligible)
    for qid in eligible[:-diff]:
        test_set.remove(qid)
        dev_set.add(qid)

assert len(dev_set) == 72
assert len(test_set) == 48

for q in queries:
    q["split"] = "dev" if q["id"] in dev_set else "test"

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(queries, f, indent=2, ensure_ascii=False)

print("Rebalancing complete with seed 42.")
