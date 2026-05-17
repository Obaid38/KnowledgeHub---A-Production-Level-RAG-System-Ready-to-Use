#!/usr/bin/env python3
"""Smoke test for Step 3 - Prompt Assembler (via pipeline_runner).

Run from the ai_server directory:
    python tests/smoke_step3.py

No pytest, no fixtures. Plain Python script.
This script prints the full assembled prompt for manual inspection.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agents.models.session import SessionContext
from ai.pipeline.pipeline_runner import run_pipeline

QUERIES = [
    "What are the steps to process a freight shortage claim and what documentation is required?",
    "What does RPOD mean and how is it different from a standard POD?",
    "Who is responsible for managing theft incidents at MPG USA and what is their contact?",
    "Who won the FIFA World Cup in 2022?",
    "Can you write a poem about ocean waves?",
    "How do I escalate a carrier dispute?",
    "What happens after an RA is approved?",
    "What about the timeline?",
    "Can you explain more about that?",
    "Can you put that in bullet points?",
]

SEP = "-" * 80


def main() -> None:
    assembled_count = 0
    skipped_count = 0
    style_counts = {
        "direct": 0,
        "procedural": 0,
        "comparative": 0,
        "exploratory": 0,
    }

    total = len(QUERIES)
    print(SEP)
    print(f"Smoke Test: Step 3 - Prompt Assembler  ({total} queries)")
    print(SEP)

    for i, query in enumerate(QUERIES, start=1):
        state = run_pipeline(query, SessionContext(session_id=f"smoke3-{i}"))
        confidence_result = state.confidence_result
        prompt_result = state.prompt_result

        print(f"\nQuery {i}/{total}: {query}")
        print(f"  confidence_result.passed      : {confidence_result.passed}")
        print(f"  confidence_result.reason      : {confidence_result.reason}")
        print(f"  prompt_result.was_skipped     : {prompt_result.was_skipped}")
        print(f"  prompt_result.skip_reason     : {prompt_result.skip_reason}")
        print(f"  prompt_result.style_used      : {prompt_result.style_used!r}")
        print(f"  prompt_result.chunk_count_used: {prompt_result.chunk_count_used}")
        print(f"  prompt_result.format_instruction:")
        print(prompt_result.format_instruction)

        if prompt_result.was_skipped:
            skipped_count += 1
        else:
            assembled_count += 1
            if prompt_result.style_used in style_counts:
                style_counts[prompt_result.style_used] += 1
            print("  prompt_result.assembled_prompt:")
            print(prompt_result.assembled_prompt)

        print(SEP)

    print(
        f"\n{assembled_count}/10 prompts assembled | "
        f"{skipped_count}/10 skipped | "
        "style distribution: "
        f"direct={style_counts['direct']} "
        f"procedural={style_counts['procedural']} "
        f"comparative={style_counts['comparative']} "
        f"exploratory={style_counts['exploratory']}"
    )


if __name__ == "__main__":
    main()
