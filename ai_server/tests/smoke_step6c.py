"""
Smoke tests for Step 6c — Pipeline Wiring + Citation Bypass + Session Persistence.

Uses fakeredis (no real Redis, Qdrant, or Ollama needed).
Install: pip install fakeredis

Run: python tests/smoke_step6c.py
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fakeredis

from ai.agents.models.session import SessionContext, Turn
from ai.pipeline.pipeline_runner import _build_citation_answer
from ai.session.redis_session_store import load_session, save_session


# ---------------------------------------------------------------------------
# Shared test citation fixtures
# ---------------------------------------------------------------------------

_SINGLE_CITATION = [
    {
        "rank": 1,
        "source_filename": "SOP.pdf",
        "page_number": 4,
        "section_heading": "3.2 Shortage Claims",
        "score_pct": 71,
        "category": "sop",
        "extraction_method": "text_extraction",
        "upload_date": None,
        "chunk_indices": [3],
    }
]

_TWO_CITATIONS = [
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
    },
    {
        "rank": 2,
        "source_filename": "DHL_Agreement.pdf",
        "page_number": 12,
        "section_heading": "8.1",
        "score_pct": 58,
        "category": "compliance",
        "extraction_method": "text_extraction",
        "upload_date": None,
        "chunk_indices": [7, 8],
    },
]


def _session_with_citations(citations):
    s = SessionContext()
    s.last_citations = citations
    return s


# ---------------------------------------------------------------------------
# TEST 1 — _build_citation_answer: page question, single source
# ---------------------------------------------------------------------------

class Test1PageSingleSource(unittest.TestCase):
    def test_page_in_result_and_filename(self):
        session = _session_with_citations(_SINGLE_CITATION)
        result = _build_citation_answer("what page was that on?", session)
        self.assertIn("page 4", result, f"Expected 'page 4' in: {result!r}")
        self.assertIn("SOP.pdf", result, f"Expected 'SOP.pdf' in: {result!r}")


# ---------------------------------------------------------------------------
# TEST 2 — _build_citation_answer: section question
# ---------------------------------------------------------------------------

class Test2SectionQuestion(unittest.TestCase):
    def test_section_heading_in_result(self):
        session = _session_with_citations(_SINGLE_CITATION)
        result = _build_citation_answer("which section covered that?", session)
        self.assertIn("3.2 Shortage Claims", result, f"Expected section heading in: {result!r}")


# ---------------------------------------------------------------------------
# TEST 3 — _build_citation_answer: document question, multiple sources
# ---------------------------------------------------------------------------

class Test3MultipleSourcesDocument(unittest.TestCase):
    def test_both_filenames_and_source_count(self):
        session = _session_with_citations(_TWO_CITATIONS)
        result = _build_citation_answer("which documents were used?", session)
        self.assertIn("SOP.pdf", result, f"Expected 'SOP.pdf' in: {result!r}")
        self.assertIn("DHL_Agreement.pdf", result, f"Expected 'DHL_Agreement.pdf' in: {result!r}")
        self.assertIn("2 source", result.lower(), f"Expected '2 source' in: {result!r}")


# ---------------------------------------------------------------------------
# TEST 4 — _build_citation_answer: last_citations is None → fallback text
# ---------------------------------------------------------------------------

class Test4NoCitations(unittest.TestCase):
    def test_fallback_when_no_citations(self):
        session = _session_with_citations(None)
        try:
            result = _build_citation_answer("what page?", session)
        except Exception as exc:
            self.fail(f"_build_citation_answer raised unexpectedly: {exc}")
        self.assertIn(
            "don't have citation",
            result.lower(),
            f"Expected fallback text in: {result!r}",
        )


# ---------------------------------------------------------------------------
# TEST 5 — Turn construction stores citations into session.last_citations
# ---------------------------------------------------------------------------

class Test5TurnStoresCitations(unittest.TestCase):
    def test_add_turn_populates_last_citations(self):
        from dataclasses import dataclass

        session = SessionContext()
        self.assertIsNone(session.last_citations)

        turn = Turn(
            query_original="What is the freight claim process?",
            query_reformulated=None,
            answer_text="You must file within 15 days.",
            answer_summary=None,
            chunk_ids=[],
            route_used="standalone",
            style_used="direct",
            timestamp="2026-04-12T00:00:00+00:00",
            query_vector=[0.1, 0.2, 0.3],
            citations=_SINGLE_CITATION,
            chunks=[],
            top_score=0.71,
        )
        session.add_turn(turn)

        self.assertIsNotNone(session.last_citations)
        self.assertEqual(len(session.last_citations), 1)
        self.assertEqual(
            session.last_citations[0]["source_filename"],
            "SOP.pdf",
            f"Expected 'SOP.pdf', got: {session.last_citations[0]!r}",
        )


# ---------------------------------------------------------------------------
# TEST 6 — Full load → save → load cycle with fakeredis
# ---------------------------------------------------------------------------

class Test6RedisRoundTrip(unittest.TestCase):
    def test_session_round_trip_preserves_citations_and_turn_count(self):
        r = fakeredis.FakeRedis()

        # First load — cache miss → fresh session
        session1 = load_session("conv-abc", r)
        self.assertEqual(session1.turn_count, 0)

        # Mutate and save
        session1.last_citations = [
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
        session1.turn_count = 1
        save_session("conv-abc", session1, r)

        # Second load — cache hit → verify state preserved
        session2 = load_session("conv-abc", r)
        self.assertEqual(session2.turn_count, 1, "turn_count not preserved across Redis round-trip")
        self.assertIsNotNone(session2.last_citations)
        self.assertEqual(
            session2.last_citations[0]["source_filename"],
            "SOP.pdf",
            f"source_filename not preserved, got: {session2.last_citations!r}",
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        Test1PageSingleSource,
        Test2SectionQuestion,
        Test3MultipleSourcesDocument,
        Test4NoCitations,
        Test5TurnStoresCitations,
        Test6RedisRoundTrip,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"\nsmoke_step6c: {passed}/{result.testsRun} pass")
    sys.exit(0 if result.wasSuccessful() else 1)
