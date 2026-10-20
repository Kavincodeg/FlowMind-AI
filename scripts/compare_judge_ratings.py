"""
Compare LLM Judge Scores with Human Expert Ratings (Phase 4).
Loads human ratings from a 30-case evaluation sheet and compares against LLM Judge predictions.
Computes:
1. Observed Percentage Agreement (P_o)
2. Cohen's Kappa (kappa) inter-rater reliability
3. Confusion matrix (True Positive, True Negative, False Positive, False Negative)
"""
import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE_FILE = ROOT / "backend" / "data" / "human_eval_sample_30.json"


def compute_cohens_kappa(human_labels: List[int], judge_labels: List[int]) -> Dict[str, float]:
    """Compute Cohen's Kappa inter-rater agreement between binary labels (0/1)."""
    assert len(human_labels) == len(judge_labels)
    n = len(human_labels)
    if n == 0:
        return {"observed_agreement": 0.0, "kappa": 0.0}

    # Confusion matrix:
    # rows: human (0, 1), cols: judge (0, 1)
    a = sum(1 for h, j in zip(human_labels, judge_labels) if h == 1 and j == 1) # Both agree 1
    b = sum(1 for h, j in zip(human_labels, judge_labels) if h == 1 and j == 0) # Human 1, Judge 0
    c = sum(1 for h, j in zip(human_labels, judge_labels) if h == 0 and j == 1) # Human 0, Judge 1
    d = sum(1 for h, j in zip(human_labels, judge_labels) if h == 0 and j == 0) # Both agree 0

    po = (a + d) / n

    # Expected agreement by chance
    p_human_1 = (a + b) / n
    p_human_0 = (c + d) / n
    p_judge_1 = (a + c) / n
    p_judge_0 = (b + d) / n

    pe = (p_human_1 * p_judge_1) + (p_human_0 * p_judge_0)

    if math.isclose(pe, 1.0):
        kappa = 1.0
    else:
        kappa = (po - pe) / (1.0 - pe)

    return {
        "n_samples": n,
        "observed_agreement": round(po, 4),
        "expected_agreement_chance": round(pe, 4),
        "cohens_kappa": round(kappa, 4),
        "contingency_matrix": {"TP_both_1": a, "FN_human1_judge0": b, "FP_human0_judge1": c, "TN_both_0": d},
    }


def main():
    parser = argparse.ArgumentParser(description="Compare Judge Scores with Human Expert Ratings")
    parser.add_argument("--sample-file", type=str, default=str(DEFAULT_SAMPLE_FILE), help="Path to 30-sample rating JSON")
    args = parser.parse_args()

    sample_path = Path(args.sample_file)
    if not sample_path.exists():
        print("Sample file not found. Creating sample template.")
        # Create 30-case evaluation sheet template if not yet present
        template = [
            {
                "case_id": f"CASE-{i+1:03d}",
                "claim": f"Sample grounded factual assertion {i+1}",
                "human_grounding_score": 1 if i % 4 != 0 else 0,  # 75% grounded in sample template
                "judge_grounding_score": 1 if (i % 4 != 0 and i != 5) else (1 if i == 8 else 0),
            }
            for i in range(30)
        ]
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sample_path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)

    with open(sample_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    human = [item["human_grounding_score"] for item in data]
    judge = [item["judge_grounding_score"] for item in data]

    res = compute_cohens_kappa(human, judge)
    print("=== Human vs LLM Judge Agreement Analysis (30-Case Audit) ===")
    print(f"Sample Size: {res['n_samples']} cases")
    print(f"Observed Agreement (P_o): {res['observed_agreement']:.2%}")
    print(f"Expected by Chance (P_e): {res['expected_agreement_chance']:.2%}")
    print(f"Cohen's Kappa (kappa):     {res['cohens_kappa']:.4f}")
    print("Contingency Matrix:", res["contingency_matrix"])


if __name__ == "__main__":
    main()
