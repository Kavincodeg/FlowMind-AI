"""
Judge vs Human Inter-Rater Reliability (Cohen's Kappa) Script (Phase 4).

Usage:
  python scripts/judge_vs_human.py --sheet backend/data/human_eval_sample_30.json
  python scripts/judge_vs_human.py --sheet backend/data/human_ratings.csv

Computes:
1. Observed Percentage Agreement (P_o)
2. Expected Agreement by Chance (P_e)
3. Cohen's Kappa (kappa)
4. Contingency Matrix (TP, TN, FP, FN)
"""
import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SHEET = ROOT / "backend" / "data" / "human_eval_sample_30.json"


def compute_cohens_kappa(human_labels: List[int], judge_labels: List[int]) -> Dict[str, Any]:
    """Calculate Cohen's Kappa inter-rater agreement for binary classifications (0/1)."""
    if len(human_labels) != len(judge_labels):
        raise ValueError(f"Mismatched count: {len(human_labels)} human vs {len(judge_labels)} judge labels.")

    n = len(human_labels)
    if n == 0:
        return {"n_samples": 0, "observed_agreement": 0.0, "cohens_kappa": 0.0}

    # Contingency matrix
    tp = sum(1 for h, j in zip(human_labels, judge_labels) if h == 1 and j == 1)
    fn = sum(1 for h, j in zip(human_labels, judge_labels) if h == 1 and j == 0)
    fp = sum(1 for h, j in zip(human_labels, judge_labels) if h == 0 and j == 1)
    tn = sum(1 for h, j in zip(human_labels, judge_labels) if h == 0 and j == 0)

    po = (tp + tn) / n

    # Marginals
    p_human_pos = (tp + fn) / n
    p_human_neg = (fp + tn) / n
    p_judge_pos = (tp + fp) / n
    p_judge_neg = (fn + tn) / n

    pe = (p_human_pos * p_judge_pos) + (p_human_neg * p_judge_neg)

    if math.isclose(pe, 1.0):
        kappa = 1.0
    else:
        kappa = (po - pe) / (1.0 - pe)

    return {
        "n_samples": n,
        "observed_agreement": round(po, 4),
        "expected_chance_agreement": round(pe, 4),
        "cohens_kappa": round(kappa, 4),
        "contingency_matrix": {
            "TP_both_grounded": tp,
            "FN_human1_judge0": fn,
            "FP_human0_judge1": fp,
            "TN_both_unsupported": tn,
        },
    }


def load_ratings(file_path: Path, factual_claims_only: bool = True) -> Tuple[List[int], List[int]]:
    """Load binary ratings from either JSON or CSV, filtering strictly to factual claims."""
    human_scores: List[int] = []
    judge_scores: List[int] = []

    if file_path.suffix.lower() == ".csv":
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if factual_claims_only and row.get("case_type") and row.get("case_type") != "factual_assertion":
                    continue
                h_val = row.get("human_grounding_score") or row.get("human_label") or row.get("human")
                j_val = row.get("judge_grounding_score") or row.get("judge_label") or row.get("judge")
                if h_val is not None and j_val is not None and str(h_val).strip() != "" and str(j_val).strip() != "":
                    human_scores.append(int(float(h_val)))
                    judge_scores.append(int(float(j_val)))
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                if factual_claims_only and item.get("case_type") and item.get("case_type") != "factual_assertion":
                    continue
                h_val = item.get("human_grounding_score", item.get("human_label", item.get("human")))
                j_val = item.get("judge_grounding_score", item.get("judge_label", item.get("judge")))
                if h_val is not None and j_val is not None and str(h_val).strip() != "" and str(j_val).strip() != "":
                    human_scores.append(int(h_val))
                    judge_scores.append(int(j_val))

    return human_scores, judge_scores


def main():
    parser = argparse.ArgumentParser(description="Evaluate Inter-Rater Reliability (Cohen's Kappa)")
    parser.add_argument("--sheet", type=str, default=str(DEFAULT_SHEET), help="Path to 30-sample rating sheet (JSON or CSV)")
    args = parser.parse_args()

    sheet_path = Path(args.sheet)
    if not sheet_path.exists():
        print(f"File not found: {sheet_path}")
        print("Creating default 30-sample template...")
        sheet_path.parent.mkdir(parents=True, exist_ok=True)
        template = [
            {
                "case_id": f"CASE-{i+1:03d}",
                "claim": f"Sample factual reasoning assertion {i+1}",
                "human_grounding_score": 1 if i % 5 != 0 else 0,
                "judge_grounding_score": 1 if (i % 5 != 0 and i != 7) else 0,
            }
            for i in range(30)
        ]
        with open(sheet_path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)

    h_scores, j_scores = load_ratings(sheet_path)
    res = compute_cohens_kappa(h_scores, j_scores)

    print("=" * 60)
    print("  FLOWMIND AI - JUDGE VS HUMAN INTER-RATER RELIABILITY")
    print("=" * 60)
    print(f"Sample count:               {res['n_samples']}")
    print(f"Observed Agreement (P_o):   {res['observed_agreement'] * 100:.2f}%")
    print(f"Expected by Chance (P_e):   {res['expected_chance_agreement'] * 100:.2f}%")
    print(f"Cohen's Kappa (kappa):      {res['cohens_kappa']:.4f}")
    print(f"Contingency Matrix:         {res['contingency_matrix']}")

    k = res["cohens_kappa"]
    if k > 0.80:
        interp = "Near Perfect Agreement"
    elif k > 0.60:
        interp = "Substantial Agreement"
    elif k > 0.40:
        interp = "Moderate Agreement"
    else:
        interp = "Fair or Poor Agreement"
    print(f"Interpretation:             {interp}")
    print("=" * 60)


if __name__ == "__main__":
    main()
