"""
Run 12-query expanded pilot benchmark with DEMO_MODE=false and in-memory MiniLM retriever.
Models:
  - Generator: llama3.1:8b (Ollama)
  - Judge: qwen2.5:7b (Ollama)
"""
import os
import sys
from pathlib import Path

# Set environment before any backend imports
os.environ["DEMO_MODE"] = "false"
os.environ["GEN_MODEL"] = "llama3.1:8b"
os.environ["JUDGE_MODEL"] = "qwen2.5:7b"
os.environ["EMBEDDING_MODEL"] = "all-MiniLM-L6-v2"

# Ensure repo root is in python path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.evaluation.runner import ComparativeEvaluator
from backend.reasoning.llm_provider import OllamaLLMProvider
from backend.retrieval.in_memory_retriever import in_memory_retrieve

def main():
    print("Starting 12-query expanded pilot with DEMO_MODE=false and in-memory MiniLM retriever...")
    llm = OllamaLLMProvider(model="llama3.1:8b", num_ctx=8192, temperature=0.3, seed=42)
    judge = OllamaLLMProvider(model="qwen2.5:7b", num_ctx=8192, temperature=0.0, seed=42)

    evaluator = ComparativeEvaluator(
        llm_provider=llm,
        temperature=0.3,
        runs=1,
        split="dev",
        is_pilot=True,
        retriever_fn=in_memory_retrieve,
    )
    # Ensure judge provider is explicitly configured
    evaluator.judge_provider = judge

    print(f"Loaded {len(evaluator.queries)} pilot queries.")
    res = evaluator.run_evaluation()
    print("Expanded pilot completed successfully!")

if __name__ == "__main__":
    main()
