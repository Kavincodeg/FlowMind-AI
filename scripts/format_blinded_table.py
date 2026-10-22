import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
run_file = ROOT / "backend" / "evaluation" / "results" / "system_a_validation_run.json"

with open(run_file, "r", encoding="utf-8") as f:
    data = json.load(f)

lines = []
lines.append("# Blinded System A Validation Table (20 Stratified Dev Queries)")
lines.append(f"**Run File Path:** `{run_file.relative_to(ROOT)}`\n")
lines.append("Instructions: Provide your label (`act`, `refuse`, or `escalate`) in the **Your Label** column. Expected outcome and mapper decision have been strictly hidden.\n")
lines.append("| Query ID | Benchmark Type | Customer Query | Verbatim System A Answer (First 400 Chars) | Your Label |")
lines.append("|:---|:---|:---|:---|:---:|")

for d in data:
    ans_clean = d["answer_first_400"].replace("\n", " ").replace("|", "\\|")
    q_clean = d["query_text"].replace("|", "\\|")
    lines.append(f"| `{d['query_id']}` | `{d['benchmark_type']}` | {q_clean} | {ans_clean} | [        ] |")

out_file = ROOT / "backend" / "evaluation" / "results" / "system_a_blinded_validation_20.md"
with open(out_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Exported blinded table successfully.")
