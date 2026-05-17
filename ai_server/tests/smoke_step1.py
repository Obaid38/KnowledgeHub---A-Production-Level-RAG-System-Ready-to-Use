#!/usr/bin/env python3
"""Smoke test for Step 1 — Retrieval Gate.

Run from the ai_server directory:
    python tests/smoke_step1.py

No pytest, no fixtures. Plain Python script.
LLM model is read from ai/agents/config/agents.yml automatically — gemma3:1b
must be pulled and ollama must be running.

Query mix:
  Queries 1-3  : clear in-domain MPG/freight/claims      → expect retrieve
  Queries 4-5  : obvious out-of-domain                   → expect refuse
  Queries 6-7  : borderline freight-adjacent but vague    → expect retrieve
  Queries 8-9  : follow-up style (short/contextual)      → expect retrieve
  Query  10    : answer_transform style                   → expect no-retrieval
"""
import os
import sys

# Ensure ai_server root is on the path when run from any working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agents.models.session import SessionContext
from ai.pipeline.step1_retrieval_gate import run_retrieval_gate

QUERIES = [
    # --- 3 clear in-domain MPG/freight/claims queries ---
    "What are the steps to process a freight shortage claim and what documentation is required?",
    "What does RPOD mean and how is it different from a standard POD?",
    "Who is responsible for managing theft incidents at MPG USA and what is their contact?",
    # --- 2 obvious out-of-domain queries ---
    "Who won the FIFA World Cup in 2022?",
    "Can you write a poem about ocean waves?",
    # --- 2 borderline queries (freight-adjacent but vague) ---
    "How do I escalate a carrier dispute?",
    "What happens after an RA is approved?",
    # --- 2 follow-up style queries ---
    "What about the timeline?",
    "Can you explain more about that?",
    # --- 1 answer_transform style query ---
    "Can you put that in bullet points?",
]

SEP = "=" * 70


def main() -> None:
    retrieved_count = 0
    refused_count = 0
    no_retrieval_count = 0

    total = len(QUERIES)
    print(SEP)
    print(f"Smoke Test: Step 1 — Retrieval Gate  ({total} queries)")
    print(SEP)

    for i, query in enumerate(QUERIES, start=1):
        session = SessionContext(session_id=f"smoke-{i}")
        print(f"\nQuery {i}/{total}: {query}")

        result = run_retrieval_gate(query, session)

        print(f"  was_refused   : {result.was_refused}")
        print(f"  was_retrieved : {result.was_retrieved}")
        print(f"  chunk_count   : {result.chunk_count}")
        print(f"  top_score     : {result.top_score:.4f}")
        print(f"  style         : {result.group1_result.style}")
        print(f"  format_type   : {result.group1_result.format_type}")
        print(f"  context_mode  : {result.group1_result.context_mode.mode}")
        print(f"  latency_ms    : {result.latency_ms:.0f}ms")
        print(SEP)

        if result.was_refused:
            refused_count += 1
        elif result.was_retrieved:
            retrieved_count += 1
        else:
            no_retrieval_count += 1

    print(f"\nSummary: {total} queries total")
    print(f"  {retrieved_count}/10 retrieved")
    print(f"  {refused_count}/10 refused")
    print(f"  {no_retrieval_count}/10 no-retrieval (answer_transform or retrieval error)")


if __name__ == "__main__":
    main()
