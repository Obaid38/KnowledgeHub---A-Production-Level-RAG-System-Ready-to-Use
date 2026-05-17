"""
Step 6 — End-to-End Session Verification

Run manually with: python tests/verify_step6_e2e.py
Requires: ollama serve, qdrant running, redis running, uvicorn app running

DO NOT auto-run this script. It requires live external services.
"""
import httpx
import json
import time

BASE = "http://localhost:8000"
SESSION_A = "e2e-test-session-001"
SESSION_B = "e2e-test-session-002"


def ask(query: str, session_id: str) -> dict:
    r = httpx.post(
        f"{BASE}/api/qa/ask",
        json={"query": query, "session_id": session_id},
        timeout=180,
    )
    return r.json()


print("=" * 60)
print("TURN 1 — Standalone question (Session A)")
r1 = ask("What are the steps to process a freight shortage claim?", SESSION_A)
print(f"  Answer preview: {r1['answer'][:100]}...")
print(f"  Citations: {json.dumps(r1.get('citations', []), indent=2)}")
print(f"  Faithfulness: {r1.get('faithfulness_passed')}")
time.sleep(2)

print("\nTURN 2 — Follow-up (Session A) — should use reformulator")
r2 = ask("What about the timeline?", SESSION_A)
print(f"  Answer preview: {r2['answer'][:100]}...")
print(f"  [Expected: answer about timeline of shortage claims, NOT empty]")
time.sleep(2)

print("\nTURN 3 — Citation lookup (Session A) — should use bypass, no Qdrant")
r3 = ask("What page was that on?", SESSION_A)
print(f"  Answer: {r3['answer']}")
print(f"  [Expected: page number from session.last_citations, ~15ms latency]")
print(f"  [Expected: model_used == 'deterministic']")
print(f"  Latency: {r3.get('latency_ms')}ms")
print(f"  Model used: {r3.get('model_used')}")
time.sleep(2)

print("\nTURN 4 — Section lookup (Session A)")
r4 = ask("Which section covered that?", SESSION_A)
print(f"  Answer: {r4['answer']}")
print(f"  [Expected: section heading from session.last_citations]")
time.sleep(2)

print("\nTURN 5 — Transform (Session A)")
r5 = ask("Put that in bullet points", SESSION_A)
print(f"  Answer preview: {r5['answer'][:100]}...")
print(f"  [Expected: reformatted answer from prior turn]")
time.sleep(2)

print("\nTURN 6 — Same citation query in NEW session (Session B)")
r6 = ask("What page was that on?", SESSION_B)
print(f"  Answer: {r6['answer']}")
print(f"  [Expected: fallback 'no citation available' — Session B has no history]")
time.sleep(2)

print("\nTURN 7 — Verify Session A TTL not reset by Session B activity")
r7 = ask("How many sources were cited?", SESSION_A)
print(f"  Answer: {r7['answer']}")
print(f"  [Expected: source count from session A's last_citations]")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("Check the above outputs manually against expected values.")
print("Citation lookup turns should show latency < 50ms.")
print("Follow-up turns should show context-aware answers, not generic ones.")
