#!/usr/bin/env python3
"""Interactive terminal demo client for the QA API.

Run this in a second terminal while FastAPI is running:
    python scripts/terminal_qa_demo.py

Behavior:
  - Prompts for a question
  - Calls POST /api/qa/ask
  - Prints only the final answer on success
  - Loops until the user types exit/quit or presses Ctrl+C
"""

from __future__ import annotations

import argparse
import sys
import uuid

import httpx


DEFAULT_API_URL = "http://localhost:8000/api/qa/ask"
DEFAULT_TIMEOUT_SECONDS = 400.0
EXIT_WORDS = {"exit", "quit", "q"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive terminal demo client for the QA API.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_API_URL,
        help=f"QA endpoint URL. Default: {DEFAULT_API_URL}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Request timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--session-id",
        default=f"terminal-demo-{uuid.uuid4().hex[:8]}",
        help="Optional session id to send with each request.",
    )
    return parser.parse_args()


def ask_question(
    client: httpx.Client,
    url: str,
    query: str,
    session_id: str,
) -> str:
    response = client.post(
        url,
        json={"query": query, "session_id": session_id},
    )
    response.raise_for_status()

    data = response.json()
    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("API response did not include a usable 'answer' field.")
    return answer.strip()


def main() -> int:
    args = parse_args()

    try:
        with httpx.Client(timeout=args.timeout) as client:
            while True:
                try:
                    query = input("Prompt: ").strip()
                except EOFError:
                    print()
                    return 0
                except KeyboardInterrupt:
                    print()
                    return 0

                if not query:
                    continue

                if query.lower() in EXIT_WORDS:
                    return 0

                try:
                    answer = ask_question(
                        client=client,
                        url=args.url,
                        query=query,
                        session_id=args.session_id,
                    )
                except httpx.HTTPStatusError as exc:
                    print(f"Request failed ({exc.response.status_code}).")
                    continue
                except httpx.RequestError as exc:
                    print(f"Could not reach the API: {exc}")
                    continue
                except ValueError as exc:
                    print(str(exc))
                    continue

                print(answer)

    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
