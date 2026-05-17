"""
Smoke tests for Step 6a — Session Serialization + Redis Store.

Uses fakeredis (no real Redis, Qdrant, or Ollama needed).
Install: pip install fakeredis

Run: python tests/smoke_step6a.py
"""
import json
import sys
import unittest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Resolve project root so imports work regardless of cwd
# ---------------------------------------------------------------------------
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agents.models.session import SessionContext, Turn
from ai.session.redis_session_store import load_session, save_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_turn(
    query: str = "What are the steps to process a freight shortage claim?",
    answer: str = "To file a shortage claim...",
    query_vector: list | None = None,
    chunk_ids: list | None = None,
    citations: list | None = None,
    top_score: float | None = None,
    route_used: str = "sop",
    style_used: str = "procedural",
) -> Turn:
    return Turn(
        query_original=query,
        query_reformulated=None,
        answer_text=answer,
        answer_summary=None,
        chunk_ids=chunk_ids if chunk_ids is not None else [],
        route_used=route_used,
        style_used=style_used,
        timestamp="2026-04-12T10:00:00Z",
        query_vector=query_vector if query_vector is not None else [0.0] * 768,
        citations=citations,
        top_score=top_score,
    )


# ---------------------------------------------------------------------------
# TEST 1 — Turn round-trips correctly through to_dict / from_dict
# ---------------------------------------------------------------------------

class TestTurnRoundTrip(unittest.TestCase):
    def test_turn_roundtrip(self) -> None:
        citations = [
            {
                "rank": 1,
                "source_filename": "SOP.pdf",
                "page_number": 4,
                "section_heading": "3.2",
                "score_pct": 71,
                "category": "sop",
                "extraction_method": "text_extraction",
                "upload_date": None,
                "chunk_indices": [3],
            }
        ]
        original = _make_turn(
            query="What are the steps to process a freight shortage claim?",
            answer="To file a shortage claim...",
            query_vector=[0.0] * 768,
            chunk_ids=[],
            citations=citations,
        )

        serialized = json.dumps(original.to_dict())
        data = json.loads(serialized)
        reconstructed = Turn.from_dict(data)

        self.assertEqual(reconstructed.query_original, original.query_original)
        self.assertEqual(reconstructed.query_vector, [0.0] * 768,
                         "query_vector must be a list, not numpy")
        self.assertIsInstance(reconstructed.query_vector, list)
        self.assertEqual(reconstructed.citations[0]["source_filename"], "SOP.pdf")
        print("  TEST 1 PASS — Turn round-trip OK")


# ---------------------------------------------------------------------------
# TEST 2 — SessionContext round-trips through to_dict / from_dict
# ---------------------------------------------------------------------------

class TestSessionContextRoundTrip(unittest.TestCase):
    def test_session_roundtrip(self) -> None:
        session = SessionContext(session_id="test-001")
        turn = _make_turn(
            citations=[
                {
                    "rank": 1,
                    "source_filename": "SOP.pdf",
                    "page_number": 4,
                    "section_heading": "3.2",
                    "score_pct": 71,
                    "category": "sop",
                    "extraction_method": "text_extraction",
                    "upload_date": None,
                    "chunk_indices": [3],
                }
            ]
        )
        session.add_turn(turn)

        serialized = json.dumps(session.to_dict())
        data = json.loads(serialized)
        reconstructed = SessionContext.from_dict(data)

        self.assertEqual(reconstructed.session_id, "test-001")
        self.assertEqual(reconstructed.turn_count, 1)
        self.assertEqual(len(reconstructed.history_window), 1)
        self.assertEqual(reconstructed.last_query, turn.query_original)
        self.assertIsNotNone(reconstructed.last_citations)
        self.assertEqual(
            reconstructed.last_citations[0]["source_filename"], "SOP.pdf"
        )
        print("  TEST 2 PASS — SessionContext round-trip OK")


# ---------------------------------------------------------------------------
# TEST 3 — Sliding window eviction at 5 turns
# ---------------------------------------------------------------------------

class TestSlidingWindow(unittest.TestCase):
    def test_eviction_at_five_turns(self) -> None:
        session = SessionContext(session_id="win-test")
        first_query = "First query — should be evicted"

        session.add_turn(_make_turn(query=first_query))
        for i in range(1, 5):
            session.add_turn(_make_turn(query=f"Query number {i + 1}"))

        self.assertEqual(len(session.history_window), 4)
        window_queries = [t.query_original for t in session.history_window]
        self.assertNotIn(first_query, window_queries,
                         "First turn must be evicted after 5 adds")
        print("  TEST 3 PASS — Sliding window eviction OK")


# ---------------------------------------------------------------------------
# TEST 4 — load_session miss returns fresh SessionContext
# ---------------------------------------------------------------------------

class TestLoadSessionMiss(unittest.TestCase):
    def test_miss_returns_fresh_session(self) -> None:
        try:
            import fakeredis
        except ImportError:
            self.skipTest("fakeredis not installed — run: pip install fakeredis")

        r = fakeredis.FakeRedis()
        result = load_session("nonexistent-session", r)

        self.assertEqual(result.turn_count, 0)
        self.assertEqual(len(result.history_window), 0)
        print("  TEST 4 PASS — load_session miss returns fresh session OK")


# ---------------------------------------------------------------------------
# TEST 5 — save then load round-trips through fakeredis
# ---------------------------------------------------------------------------

class TestSaveLoadRoundTrip(unittest.TestCase):
    def test_save_then_load(self) -> None:
        try:
            import fakeredis
        except ImportError:
            self.skipTest("fakeredis not installed — run: pip install fakeredis")

        r = fakeredis.FakeRedis()

        session = SessionContext(session_id="sess-001")
        turn = _make_turn(
            citations=[
                {
                    "rank": 1,
                    "source_filename": "MPG_SOP.pdf",
                    "page_number": 2,
                    "section_heading": "1.1",
                    "score_pct": 80,
                    "category": "sop",
                    "extraction_method": "text_extraction",
                    "upload_date": None,
                    "chunk_indices": [0],
                }
            ]
        )
        session.add_turn(turn)

        save_session("sess-001", session, r)
        loaded = load_session("sess-001", r)

        self.assertEqual(loaded.turn_count, 1)
        self.assertEqual(loaded.last_query, turn.query_original)
        self.assertIsNotNone(loaded.last_citations)
        self.assertEqual(
            loaded.last_citations[0]["source_filename"],
            turn.citations[0]["source_filename"],
        )
        print("  TEST 5 PASS — save/load round-trip through fakeredis OK")


# ---------------------------------------------------------------------------
# TEST 6 — Redis failure on load is silent
# ---------------------------------------------------------------------------

class TestLoadFailureSilent(unittest.TestCase):
    def test_redis_load_failure_silent(self) -> None:
        broken_client = MagicMock()
        broken_client.get.side_effect = ConnectionError("Redis is down")

        result = load_session("any-id", broken_client)

        self.assertIsInstance(result, SessionContext)
        self.assertEqual(result.turn_count, 0)
        print("  TEST 6 PASS — Redis load failure is silent OK")


# ---------------------------------------------------------------------------
# TEST 7 — Redis failure on save is silent
# ---------------------------------------------------------------------------

class TestSaveFailureSilent(unittest.TestCase):
    def test_redis_save_failure_silent(self) -> None:
        broken_client = MagicMock()
        broken_client.setex.side_effect = ConnectionError("Redis is down")

        session = SessionContext(session_id="any-id")
        session.add_turn(_make_turn())

        # Must not raise
        save_session("any-id", session, broken_client)
        print("  TEST 7 PASS — Redis save failure is silent OK")


# ---------------------------------------------------------------------------
# TEST 8 — session_id=None skips all Redis
# ---------------------------------------------------------------------------

class TestNoneSessionIdSkipsRedis(unittest.TestCase):
    def test_none_session_id_skips_redis(self) -> None:
        try:
            import fakeredis
        except ImportError:
            self.skipTest("fakeredis not installed — run: pip install fakeredis")

        r = fakeredis.FakeRedis()

        # load_session with None → fresh session, no Redis call
        result = load_session(None, r)
        self.assertIsInstance(result, SessionContext)
        self.assertEqual(result.turn_count, 0)

        # save_session with None → no-op, no exception
        session = SessionContext(session_id="ignored")
        save_session(None, session, r)

        # Confirm nothing was written to Redis
        all_keys = r.keys("*")
        self.assertEqual(len(all_keys), 0, "No Redis keys should exist")

        print("  TEST 8 PASS — session_id=None skips Redis OK")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("smoke_step6a — Session Serialization + Redis Store")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestTurnRoundTrip,
        TestSessionContextRoundTrip,
        TestSlidingWindow,
        TestLoadSessionMiss,
        TestSaveLoadRoundTrip,
        TestLoadFailureSilent,
        TestSaveFailureSilent,
        TestNoneSessionIdSkipsRedis,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n" + "=" * 60)
        print("All 8 tests passed.")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"\nFailed: {len(result.failures)} failure(s), {len(result.errors)} error(s)")
        sys.exit(1)
