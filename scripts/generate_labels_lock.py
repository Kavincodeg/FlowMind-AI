"""
FlowMind AI - Label Lock Tool (Phase 4).
Calculates and writes canonical SHA-256 checksum of:
- All held-out test cases (48 cases)
- All adversarial cases (20 cases)
Writes to LABELS.lock once approved by lead reviewer.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"
LOCK_FILE = ROOT / "backend" / "data" / "LABELS.lock"


def compute_labels_checksum() -> str:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)

    # Filter target cases: held-out test cases + adversarial cases
    target_cases = [q for q in queries if q.get("split") == "test" or q.get("benchmark_type") == "adversarial"]
    target_cases.sort(key=lambda x: x.get("id", x.get("query_id")))

    canonical_data = []
    for q in target_cases:
        canonical_data.append({
            "id": q.get("id"),
            "query_text": q.get("query_text"),
            "split": q.get("split"),
            "type": q.get("benchmark_type"),
            "expected_outcome": q.get("expected_outcome"),
            "expected_action_type": q.get("expected_action_type"),
            "expected_risk_level": q.get("expected_risk_level"),
            "expected_chunk_ids": sorted(q.get("expected_chunk_ids", [])),
        })

    serialized = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write_lock_file():
    chk = compute_labels_checksum()
    LOCK_FILE.write_text(f"{chk}\n", encoding="utf-8")
    print(f"Computed SHA-256: {chk}")
    print("LABELS.lock generated successfully.")


def verify_lock_file() -> bool:
    if not LOCK_FILE.exists():
        return False
    expected = LOCK_FILE.read_text(encoding="utf-8").strip()
    current = compute_labels_checksum()
    return expected == current


if __name__ == "__main__":
    if "--verify" in sys.argv:
        if verify_lock_file():
            print("LABELS.lock verified: MATCH")
            sys.exit(0)
        else:
            print("LABELS.lock verification: FAILED OR MISSING")
            sys.exit(1)
    else:
        write_lock_file()
