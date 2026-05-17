#!/usr/bin/env python3
"""Smoke test for Step 2 — Confidence Gate (via pipeline_runner).

Run from the ai_server directory:
    python tests/smoke_step2.py

No pytest, no fixtures. Plain Python script.
Thresholds are read from ai/agents/config/agents.yml automatically.

Query mix (same as smoke_step1.py — self-contained):
  Queries 1-3  : clear in-domain MPG/freight/claims      → expect retrieve + pass gate
  Queries 4-5  : obvious out-of-domain                   → expect refuse
  Queries 6-7  : borderline freight-adjacent but vague    → expect retrieve, gate varies
  Queries 8-9  : follow-up style (short/contextual)      → expect retrieve, gate varies
  Query  10    : answer_transform style                   → expect skipped gate
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agents.models.session import SessionContext
from ai.pipeline.pipeline_runner import run_pipeline

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
    gate_passed = 0
    gate_refused = 0
    gate_below = 0
    gate_skipped = 0

    total = len(QUERIES)
    print(SEP)
    print(f"Smoke Test: Step 2 — Confidence Gate  ({total} queries)")
    print(SEP)

    for i, query in enumerate(QUERIES, start=1):
        session = SessionContext(session_id=f"smoke2-{i}")
        print(f"\nQuery {i}/{total}: {query}")

        state = run_pipeline(query, session)
        r = state.retrieval_result
        c = state.confidence_result

        print(f"  [Step 1]")
        print(f"    was_refused   : {r.was_refused}")
        print(f"    was_retrieved : {r.was_retrieved}")
        print(f"    chunk_count   : {r.chunk_count}")
        print(f"    top_score     : {r.top_score:.4f}")
        print(f"  [Step 2]")
        print(f"    passed        : {c.passed}")
        print(f"    threshold_used: {c.threshold_used:.3f}")
        print(f"    style_used    : {c.style_used!r}")
        print(f"    reason        : {c.reason}")
        print(SEP)

        if c.reason == "passed":
            gate_passed += 1
        elif r.was_refused:
            gate_refused += 1
        elif c.reason == "skipped_no_retrieval":
            gate_skipped += 1
        else:
            gate_below += 1

    print(f"\nSummary: {total} queries total")
    print(f"  {gate_passed}/10  passed confidence gate   → will proceed to answer generation")
    print(f"  {gate_refused}/10  refused by Group 1        → out-of-domain")
    print(f"  {gate_below}/10  below threshold / no chunks → low-confidence retrieval")
    print(f"  {gate_skipped}/10  skipped gate               → transform path or no retrieval")


if __name__ == "__main__":
    main()
