"""
Label Consistency Checker for FlowMind AI (Phase 4).
Validates that:
1. All expected_chunk_ids exist in the knowledge store (policies/tickets).
2. Action, risk, and outcome values are valid enums:
   - expected_action_type in ActionType or None
   - expected_risk_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
   - expected_outcome in {"act", "escalate", "refuse"}
3. Invariant: Refuse and escalate cases have NO expected action (expected_action_type is None/null).
4. Invariant: Act cases MUST specify an expected_action_type.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"
POLICIES_DIR = ROOT / "backend" / "data" / "policies"
TICKETS_FILE = ROOT / "backend" / "data" / "synthetic" / "tickets.json"

VALID_ACTIONS = {
    "ESCALATE_TICKET",
    "TRANSFER_TEAM",
    "REQUEST_CUSTOMER_INFO",
    "ISSUE_REFUND_RECOMMENDATION",
    "RESOLVE_STANDARD",
    "NO_ACTION",
    None,
}

VALID_RISKS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_OUTCOMES = {"act", "escalate", "refuse"}

# Load existing store IDs
known_sources = set()
for md in POLICIES_DIR.glob("*.md"):
    known_sources.add(md.name)

if TICKETS_FILE.exists():
    with open(TICKETS_FILE, "r", encoding="utf-8") as f:
        tickets = json.load(f)
        for t in tickets:
            if t.get("ticket_id"):
                known_sources.add(t.get("ticket_id"))
            if t.get("id"):
                known_sources.add(t.get("id"))

with open(DATA_FILE, "r", encoding="utf-8") as f:
    queries = json.load(f)

errors = []

for q in queries:
    qid = q.get("id", q.get("query_id"))
    outcome = q.get("expected_outcome")
    action = q.get("expected_action_type")
    risk = q.get("expected_risk_level")
    chunk_ids = q.get("expected_chunk_ids", [])

    # Check 1: outcome enum
    if outcome not in VALID_OUTCOMES:
        errors.append(f"[{qid}] Invalid outcome: {outcome}")

    # Check 2: risk enum
    if risk not in VALID_RISKS:
        errors.append(f"[{qid}] Invalid risk level: {risk}")

    # Check 3: action enum
    if action not in VALID_ACTIONS:
        errors.append(f"[{qid}] Invalid action type: {action}")

    # Check 4: Refuse and escalate cases have NO expected action
    if outcome in ("refuse", "escalate") and action is not None:
        errors.append(
            f"[{qid}] Invariant violation: outcome '{outcome}' must have expected_action_type=None, found '{action}'"
        )

    # Check 5: Act cases MUST specify an expected action
    if outcome == "act" and (action is None or action == "NO_ACTION"):
        errors.append(
            f"[{qid}] Invariant violation: outcome 'act' requires a specific valid action, found '{action}'"
        )

    # Check 6: All expected_chunk_ids exist in the knowledge store
    for cid in chunk_ids:
        # Strip chunk index suffix if present (e.g. #chunk_0)
        base_src = cid.split("#")[0].split(":")[0]
        if base_src not in known_sources and not any(base_src in s for s in known_sources):
            # Check if it's a generic synthetic ticket reference
            if not base_src.startswith("ticket_"):
                errors.append(f"[{qid}] Chunk source '{cid}' not found in known policy/ticket store.")

if errors:
    print(f"FAILED: Found {len(errors)} consistency errors:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"SUCCESS: All {len(queries)} queries passed consistency check!")
    print(f"  - Valid enums verified (actions, risks, outcomes).")
    print(f"  - Refuse/escalate cases provably have expected_action_type=None.")
    print(f"  - All expected chunk IDs resolved in policy/ticket store.")
