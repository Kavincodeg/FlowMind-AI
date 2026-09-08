"""
FlowMind AI - Plain-RAG Baseline Service (Phase 2)
Implements the comparison baseline: retrieve evidence + answer query only.
No action recommendation, no approval gating, no workflow execution.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from backend.baseline.models import BaselineAnswer, BaselineQuery
from backend.baseline.prompts import BASELINE_SYSTEM_PROMPT, build_baseline_prompt
from backend.reasoning.llm_provider import LLMProvider, get_llm_provider
from backend.retrieval.models import RetrievalQuery, RetrievalResult
from backend.retrieval.retriever import retrieve as default_retrieve

logger = logging.getLogger(__name__)


class PlainRAGBaseline:
    """
    Comparison baseline system that only retrieves documents and answers questions.
    Demonstrates the standard RAG paradigm (retrieve + answer) to compare against FlowMind's
    closed-loop (retrieve -> reason -> recommend -> approve -> act -> audit).
    """

    def __init__(
        self,
        retriever_fn: Optional[Callable[[RetrievalQuery], RetrievalResult]] = None,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.retrieve = retriever_fn or default_retrieve
        self.llm_provider = llm_provider or get_llm_provider()

    def answer(self, query: BaselineQuery) -> BaselineAnswer:
        """Execute retrieve + answer pipeline without workflow recommendations."""
        t0 = time.perf_counter()

        # Step 1: Retrieval
        retrieval_query = RetrievalQuery(
            query_text=query.query_text,
            top_k=query.top_k,
            filters=query.filters,
            score_threshold=query.score_threshold,
        )
        retrieval_res = self.retrieve(retrieval_query)
        retrieval_ms = retrieval_res.retrieval_time_ms

        if not retrieval_res.chunks:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return BaselineAnswer(
                query_text=query.query_text,
                answer="I could not find any relevant information in the knowledge base to answer your question.",
                citations=[],
                retrieved_chunks_count=0,
                retrieval_time_ms=retrieval_ms,
                generation_time_ms=round(elapsed_ms - retrieval_ms, 2),
                model_used=self.llm_provider.__class__.__name__,
            )

        # Step 2: Formulate prompt
        user_prompt = build_baseline_prompt(
            query_text=query.query_text,
            context=retrieval_res.combined_context,
        )

        # Step 3: LLM Generation
        t_gen = time.perf_counter()
        raw_answer = self.llm_provider.generate(
            prompt=user_prompt,
            system_prompt=BASELINE_SYSTEM_PROMPT,
            temperature=0.0,
        )
        gen_ms = (time.perf_counter() - t_gen) * 1000

        return BaselineAnswer(
            query_text=query.query_text,
            answer=raw_answer.strip(),
            citations=retrieval_res.citations,
            retrieved_chunks_count=len(retrieval_res.chunks),
            retrieval_time_ms=round(retrieval_ms, 2),
            generation_time_ms=round(gen_ms, 2),
            model_used=self.llm_provider.__class__.__name__,
        )


def answer_baseline_query(
    query: BaselineQuery,
    retriever_fn: Optional[Callable[[RetrievalQuery], RetrievalResult]] = None,
    llm_provider: Optional[LLMProvider] = None,
) -> BaselineAnswer:
    """Convenience function to query the Plain-RAG baseline."""
    baseline = PlainRAGBaseline(retriever_fn=retriever_fn, llm_provider=llm_provider)
    return baseline.answer(query)
