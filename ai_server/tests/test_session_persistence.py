"""
Session persistence integration test — hits FastAPI /api/qa/ask directly.

Requirements: uvicorn + Qdrant + Ollama + Redis all running.

Usage:
  cd ai_server
  python tests/test_session_persistence.py

Optional flags:
  --base   FastAPI base URL (default: http://localhost:8000)
  --col    Qdrant collection to search (default: sop)
  --q1     Override the first question

What this tests:
  1. Standalone question — normal RAG path, citations saved to session
  2. Follow-up question  — Stage 2 detects retrieval_followup, Stage 2a reformulates
  3. Citation lookup     — bypasses Qdrant + LLM, answered from session.last_citations
  4. Section lookup      — second citation bypass, different keyword
  5. Fresh session       — same citation query, different session_id → fallback answer
"""
import argparse
import json
import sys
import time

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://localhost:8000", help="FastAPI base URL")
parser.add_argument("--col",  default="sop",                   help="Qdrant collection")
parser.add_argument("--q1",   default="What are the steps to process a freight shortage claim?",
                    help="First question (standalone RAG)")
args = parser.parse_args()

BASE       = args.base.rstrip("/")
COLLECTION = args.col
SESSION_A  = f"test-session-A-{int(time.time())}"
SESSION_B  = f"test-session-B-{int(time.time())}"

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
INFO = "\033[94m INFO\033[0m"

results = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ask(query: str, session_id: str, collection: str | None = None) -> dict:
    payload = {"query": query, "session_id": session_id}
    if collection:
        payload["collection_filter"] = [collection]
    r = httpx.post(f"{BASE}/api/qa/ask", json=payload, timeout=300)
    r.raise_for_status()
    return r.json()


def check(label: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    results.append(condition)
    msg = f"  {status}  {label}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# TURN 1 — Standalone RAG question
# ---------------------------------------------------------------------------
section("TURN 1 — Standalone question (Session A)")
print(f"  query:      {args.q1!r}")
print(f"  session_id: {SESSION_A}")
print(f"  collection: {COLLECTION}")

r1 = ask(args.q1, SESSION_A, COLLECTION)
print(f"\n  answer:     {r1['answer'][:120]}...")
print(f"  model_used: {r1.get('model_used')}")
print(f"  latency_ms: {r1.get('latency_ms'):.0f}ms")
print(f"  citations:  {json.dumps(r1.get('citations', [])[:1], indent=4)}")
print(f"  session_id: {r1.get('session_id')}")

check("was_generated is True",        r1.get("was_generated") is True)
check("citations list is non-empty",  len(r1.get("citations", [])) > 0,
      "If empty, confidence gate may have blocked retrieval — check top_score")
check("session_id echoed correctly",  r1.get("session_id") == SESSION_A)

time.sleep(1)

# ---------------------------------------------------------------------------
# TURN 2 — Follow-up (same session, session B still empty)
# ---------------------------------------------------------------------------
section("TURN 2 — Follow-up question (Session A)")
followup = "What about the timeline for that?"
print(f"  query: {followup!r}")

r2 = ask(followup, SESSION_A, COLLECTION)
print(f"\n  answer:     {r2['answer'][:120]}...")
print(f"  model_used: {r2.get('model_used')}")
print(f"  latency_ms: {r2.get('latency_ms'):.0f}ms")

check("was_generated is True",  r2.get("was_generated") is True,
      "If False, follow-up was not reformulated correctly or confidence gate failed")
check("model_used is not 'deterministic'",  r2.get("model_used") != "deterministic",
      "Follow-ups go through LLM — should NOT be the citation bypass")

time.sleep(1)

# ---------------------------------------------------------------------------
# TURN 3 — Citation lookup bypass (same session)
# ---------------------------------------------------------------------------
section("TURN 3 — Citation lookup (Session A) — expects bypass")
citation_q = "What page was that on?"
print(f"  query: {citation_q!r}")
print(f"  [Expected: model_used='deterministic', latency <50ms]")

r3 = ask(citation_q, SESSION_A)
print(f"\n  answer:     {r3['answer']}")
print(f"  model_used: {r3.get('model_used')}")
print(f"  latency_ms: {r3.get('latency_ms'):.1f}ms")

check("model_used is 'deterministic'",  r3.get("model_used") == "deterministic",
      f"Got: {r3.get('model_used')!r} — session may not have citations from Turn 1")
check("answer contains page or source info",
      any(w in r3["answer"].lower() for w in ["page", "source", "found in", "drew from", "came from"]),
      f"Got: {r3['answer']!r}")
_lat3 = r3.get("latency_ms")
check("latency < 200ms (bypass)",  _lat3 is not None and _lat3 < 200,
      f"Got: {_lat3:.1f}ms — high latency suggests LLM was called")

time.sleep(1)

# ---------------------------------------------------------------------------
# TURN 4 — Section lookup bypass (same session)
# ---------------------------------------------------------------------------
section("TURN 4 — Section lookup (Session A) — expects bypass")
section_q = "Which section covered that?"
print(f"  query: {section_q!r}")

r4 = ask(section_q, SESSION_A)
print(f"\n  answer:     {r4['answer']}")
print(f"  model_used: {r4.get('model_used')}")

check("model_used is 'deterministic'",  r4.get("model_used") == "deterministic")
check("answer contains section info",
      any(w in r4["answer"].lower() for w in ["section", "§", "chapter", "heading", "covered"]),
      f"Got: {r4['answer']!r}")

time.sleep(1)

# ---------------------------------------------------------------------------
# TURN 5 — Same citation query in a FRESH session (Session B)
# ---------------------------------------------------------------------------
section("TURN 5 — Citation query in fresh session (Session B)")
print(f"  query:      {citation_q!r}")
print(f"  session_id: {SESSION_B}")
print(f"  [Expected: fallback 'no citation' answer — Session B has no history]")

r5 = ask(citation_q, SESSION_B)
print(f"\n  answer:     {r5['answer']}")
print(f"  model_used: {r5.get('model_used')}")

check("answer is NOT the deterministic citation response",
      "don't have citation" in r5["answer"].lower()
      or r5.get("model_used") != "deterministic",
      f"Got model_used={r5.get('model_used')!r}, answer={r5['answer'][:80]!r}")

time.sleep(1)

# ---------------------------------------------------------------------------
# TURN 6 — Answer transform (Session A, has history from Turns 1–4)
# ---------------------------------------------------------------------------
section("TURN 6 — Answer transform (Session A) — expects LLM reformat")
transform_q = "put that in bullet points"
print(f"  query: {transform_q!r}")
print(f"  [Expected: model_used=LLM model, was_generated=True]")

r6 = ask(transform_q, SESSION_A)
print(f"\n  answer:     {r6['answer'][:120]}...")
print(f"  model_used: {r6.get('model_used')}")
print(f"  latency_ms: {r6.get('latency_ms'):.0f}ms")

check("was_generated is True",
      r6.get("was_generated") is True,
      "If False, answer_transform bypass may not be implemented or LLM failed")
check("model_used is NOT 'deterministic'",
      r6.get("model_used") != "deterministic",
      f"Got: {r6.get('model_used')!r} — transform must go through LLM")
check("answer is non-empty",
      len(r6.get("answer", "")) > 10,
      f"Got: {r6.get('answer', '')[:80]!r}")

time.sleep(1)

# ---------------------------------------------------------------------------
# TURN 7 — Answer transform on a fresh session (Session C, no history)
# ---------------------------------------------------------------------------
section("TURN 7 — Answer transform on empty session (Session C) — expects fallback")
SESSION_C = f"test-session-C-{int(time.time())}"
print(f"  query:      {transform_q!r}")
print(f"  session_id: {SESSION_C}")
print(f"  [Expected: was_generated=False, no prior answer message]")

r7 = ask(transform_q, SESSION_C)
print(f"\n  answer:     {r7['answer'][:120]}")
print(f"  model_used: {r7.get('model_used')}")

check("was_generated is False (no prior answer)",
      r7.get("was_generated") is False,
      f"Got: was_generated={r7.get('was_generated')}, answer={r7.get('answer','')[:80]!r}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'═' * 60}")
passed = sum(results)
total  = len(results)
color  = "\033[92m" if passed == total else "\033[91m"
print(f"  {color}{passed}/{total} checks passed\033[0m")

if passed < total:
    print("\n  Tips:")
    print("  - If Turn 1 has no citations: check top_score in response.")
    print("    Low score (<0.4) → confidence gate blocked retrieval.")
    print("    Try a different --q1 or --col.")
    print("  - If Turn 3 model_used != 'deterministic': Turn 1 citations")
    print("    were not saved to Redis. Check REDIS_URL env var and Redis health.")
    print("  - If all turns fail: confirm uvicorn, Qdrant, Ollama, Redis are running.")

print(f"{'═' * 60}\n")
sys.exit(0 if passed == total else 1)
