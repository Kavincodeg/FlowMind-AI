"""
Spot-check 10 System A answers with rule-based deterministic outcome mapping.
Demonstrates deterministic mapping of free-text into:
- refuse
- escalate
- act
"""
import json
import re
from pathlib import Path
from backend.baseline.service import PlainRAGBaseline
from backend.baseline.models import BaselineQuery
from backend.reasoning.llm_provider import OllamaLLMProvider
from backend.retrieval.mock_retriever import mock_retrieve

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "backend" / "data" / "test_queries.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    all_queries = json.load(f)

dev_queries = [q for q in all_queries if q.get("split") == "dev"]

# Pick 10 representative queries across types
selected_10 = []
for qid in ["Q001", "Q002", "Q015", "Q033", "Q045", "Q051", "Q074", "Q080", "Q086", "Q101"]:
    matches = [q for q in dev_queries if (q.get("id") or q.get("query_id")) == qid]
    if matches:
        selected_10.append(matches[0])

def map_baseline_free_text_to_outcome(text: str) -> str:
    """
    Deterministic rule-based mapper converting Plain-RAG free-text into act/escalate/refuse:
    1. Refuse: explicit statements of inability to answer, insufficient info, policy violation, or declining unapproved commands.
    2. Escalate: explicit mention of escalation to higher tiers (L2/L3/Manager/Legal).
    3. Act: standard resolution, informational response, or direct policy advice.
    """
    tl = text.lower()
    
    # 1. Refusal patterns
    refusal_patterns = [
        r"could not find any relevant information",
        r"cannot find (any )?(relevant )?information",
        r"no relevant (information|policy|ticket|documents)",
        r"insufficient (evidence|information)",
        r"do not have enough information",
        r"unable to (locate|assist|fulfill|process)",
        r"cannot (assist|fulfill|process|override|grant)",
        r"system override.*(cannot|not permitted|refused)",
        r"i cannot fulfill this request",
        r"violates.*(policy|guideline|security)",
    ]
    if any(re.search(p, tl) for p in refusal_patterns):
        return "refuse"
        
    # 2. Escalation patterns
    escalation_patterns = [
        r"\bescalat",
        r"tier[ -]?(2|3|two|three)",
        r"level[ -]?(2|3|two|three)",
        r"\bl[23]\b",
        r"manager review",
        r"team lead review",
        r"legal (&|and) compliance",
        r"transfer.*(manager|team lead|supervisor)",
    ]
    if any(re.search(p, tl) for p in escalation_patterns):
        return "escalate"
        
    # 3. Default to Act
    return "act"

print("=" * 80)
print("SYSTEM A FREE-TEXT TO OUTCOME DETERMINISTIC MAPPING SPOT-CHECK (10 QUERIES)")
print("=" * 80)

baseline = PlainRAGBaseline(retriever_fn=mock_retrieve, llm_provider=OllamaLLMProvider(model="llama3.1:8b", temperature=0.0))

results = []
for q in selected_10:
    qid = q.get("id") or q.get("query_id")
    q_text = q["query_text"]
    exp_outcome = q.get("expected_outcome")
    
    ans = baseline.answer(BaselineQuery(query_text=q_text))
    mapped = map_baseline_free_text_to_outcome(ans.answer)
    match = (mapped == exp_outcome)
    
    print(f"\nQuery [{qid}] ({q.get('benchmark_type')}): \"{q_text}\"")
    print(f"Expected Outcome: {exp_outcome}")
    print(f"System A Text:\n  \"{ans.answer.strip()}\"")
    print(f"Mapped Label: -> '{mapped}' (Match Expected: {match})")
    results.append({
        "query_id": qid,
        "query_text": q_text,
        "expected_outcome": exp_outcome,
        "mapped_outcome": mapped,
        "raw_text": ans.answer.strip(),
        "is_match": match
    })

with open(ROOT / "backend" / "data" / "system_a_spotcheck_10.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
