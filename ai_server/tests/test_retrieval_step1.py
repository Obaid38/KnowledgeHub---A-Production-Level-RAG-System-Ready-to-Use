#!/usr/bin/env python3
"""Retrieval Step 1 — Manual validation script.

Run with:
    python tests/test_retrieval_step1.py [--base-url http://localhost:8000]

Tests the POST /api/qa/ask endpoint against the ingested MPG USA Logistics &
Claims SOP. The three queries target specific pages/sections of that document
to validate that chunking and table serialization worked correctly.

RETRIEVAL VERDICT at the end:
  PASS — all 3 queries returned ≥1 chunk above threshold → ready for LLM wiring
  FAIL — one or more queries returned 0 chunks → investigate ingestion/chunking
"""

import argparse
import sys

import httpx

BASE_URL = "http://localhost:8000"
CHUNK_PREVIEW_LEN = 300

TEST_QUERIES = [
    {
        "label": "Query 1 — SOP Procedure (Section 4, Page 8)",
        "description": (
            "Tests retrieval of a multi-step procedure from SOP-01."
        ),
        "payload": {
            "query": "What are the steps to process a freight shortage claim and what documentation is required?",
            "collection": "sop",
            "access_level": None,
        },
    },
    {
        "label": "Query 2 — Roles Table (Page 7)",
        "description": (
            "Tests retrieval from the Roles & Responsibilities table. "
            "The Logistics Security row (logsec@sea.samsung.com) is the target. "
            "Validates that table content was serialized and chunked correctly."
        ),
        "payload": {
            "query": "Who is responsible for managing theft incidents at MPG and what is their contact?",
            "collection": "sop",
            "access_level": None,
        },
    },
    {
        "label": "Query 3 — Definitions/Abbreviations Table (Page 6)",
        "description": (
            "Tests retrieval from the Definitions & Abbreviations table. "
            "Targets the RA, RPOD, and BOL rows specifically. "
            "Pure table lookup — validates table serialization quality."
        ),
        "payload": {
            "query": "What does RPOD mean and how is it different from POD? Also what is a BOL?",
            "collection": "sop",
            "access_level": None,
        },
    },
]

SEPARATOR = "═" * 60
THIN_SEP = "─" * 45


def run_tests(base_url: str) -> int:
    """Run all test queries. Returns number of failing queries."""
    client = httpx.Client(base_url=base_url, timeout=180.0)
    failures: list[str] = []

    for i, test in enumerate(TEST_QUERIES, start=1):
        label = test["label"]
        description = test["description"]
        payload = test["payload"]

        print(f"\n{SEPARATOR}")
        print(f"{label}")
        print(description)
        print()
        print(f"  Request → collection: {payload['collection']}")
        print(f"            query: \"{payload['query'][:80]}{'...' if len(payload['query']) > 80 else ''}\"")
        print()

        try:
            resp = client.post("/api/qa/ask", json=payload)
        except httpx.ConnectError:
            print(f"  ❌  CONNECTION FAILED — is the server running at {base_url}?")
            failures.append(label)
            continue

        if resp.status_code != 200:
            print(f"  ❌  HTTP {resp.status_code}: {resp.text[:200]}")
            failures.append(label)
            continue

        body = resp.json()
        result_count = body.get("result_count", 0)
        top_score = body.get("top_score", 0.0)
        latency_ms = body.get("latency_ms", 0.0)
        threshold = body.get("threshold_applied", 0.0)
        below = body.get("below_threshold_count", 0)
        chunks = body.get("chunks", [])

        status_icon = "✅" if result_count > 0 else "❌"
        print(f"  {status_icon}  {result_count} chunks returned | top_score={top_score:.4f} | latency={latency_ms:.0f}ms")
        print(f"  threshold_applied: {threshold} | below_threshold_rejected: {below}")

        if result_count == 0:
            print()
            print("  No chunks passed the threshold.")
            print("  → If this is Query 2 or 3, the issue is likely in table serialization during ingestion.")
            failures.append(label)
        else:
            for j, chunk in enumerate(chunks, start=1):
                score = chunk.get("score", 0.0)
                source = chunk.get("source_filename", "unknown")
                heading = chunk.get("section_heading", "")
                page = chunk.get("page_number")
                text = chunk.get("chunk_text", "")
                page_str = f" | page={page}" if page is not None else ""
                print()
                print(f"  Chunk {j} | score={score:.4f} | source={source} | heading={heading}{page_str}")
                print(f"  {THIN_SEP}")
                preview = text[:CHUNK_PREVIEW_LEN].replace("\n", " ")
                if len(text) > CHUNK_PREVIEW_LEN:
                    preview += "..."
                print(f"  {preview}")

    print(f"\n{SEPARATOR}")
    if not failures:
        print("RETRIEVAL VERDICT: PASS ✅  (all 3 queries returned ≥1 chunk above threshold)")
        print("→ Retrieval layer is ready for LLM wiring (Step 2).")
    else:
        failed_names = ", ".join(f"Query {TEST_QUERIES.index(next(t for t in TEST_QUERIES if t['label'] == f)) + 1}" for f in failures)
        print(f"RETRIEVAL VERDICT: FAIL ❌  ({failed_names} returned 0 chunks — check table serialization or ingestion)")
        if any("Query 2" in f or "Query 3" in f for f in [failed_names]):
            print("→ Queries 2 and 3 target table content. A failure here indicates the table")
            print("  serializer did not produce retrievable chunks — this is an ingestion issue,")
            print("  NOT a retrieval layer bug.")
    print()

    return len(failures)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval Step 1 validation script")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"FastAPI base URL (default: {BASE_URL})",
    )
    args = parser.parse_args()

    failure_count = run_tests(args.base_url)
    sys.exit(0 if failure_count == 0 else 1)


if __name__ == "__main__":
    main()
