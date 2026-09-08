"""
FlowMind AI - Plain-RAG Baseline (Phase 2)
Comparison system: retrieves evidence and answers without recommendations or approval gating.
"""
from backend.baseline.models import BaselineAnswer, BaselineQuery
from backend.baseline.service import PlainRAGBaseline, answer_baseline_query

__all__ = [
    "BaselineQuery",
    "BaselineAnswer",
    "PlainRAGBaseline",
    "answer_baseline_query",
]
