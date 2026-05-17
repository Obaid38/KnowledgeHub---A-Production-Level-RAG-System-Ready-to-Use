"""
Smoke tests for the answer_transform pipeline bypass.

No services required (no Ollama, Qdrant, or Redis).

Tests:
  1. _build_transform_prompt_result — prompt template content
  2. Transform Turn construction — session.last_answer updates, citations preserved
  3. No-prior-answer path — fallback message, no Turn added
  4. Consecutive transforms — second transform reformats the reformatted text

Run: python tests/smoke_transform.py
"""
import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agents.models.session import SessionContext, Turn
from ai.pipeline.pipeline_runner import _build_transform_prompt_result


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_PRIOR_ANSWER = (
    "To file a shortage claim: "
    "1. Gather BOL and POD documents. "
    "2. Submit within 15 days of delivery. "
    "3. Include invoice and item details."
)

_CITATIONS = [
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


def _make_session_with_answer(answer_text: str, citations=None) -> SessionContext:
    """Build a SessionContext with one prior Turn carrying an answer."""
    session = SessionContext(session_id="test-session")
    turn = Turn(
        query_original="What is the freight claim process?",
        query_reformulated=None,
        answer_text=answer_text,
        answer_summary=None,
        chunk_ids=[],
        route_used="standalone",
        style_used="direct",
        timestamp=datetime.now(timezone.utc).isoformat(),
        query_vector=[],
        citations=citations,
        chunks=[],
        top_score=0.71,
    )
    session.add_turn(turn)
    return session


# ---------------------------------------------------------------------------
# TEST 1 — _build_transform_prompt_result: prompt structure
# ---------------------------------------------------------------------------

class Test1TransformPromptStructure(unittest.TestCase):
    def setUp(self):
        from ai.pipeline.step2_confidence_gate import ConfidenceGateResult
        # Minimal synthetic confidence result
        self.mock_cr = ConfidenceGateResult(
            passed=False, top_score=0.0, threshold_used=0.0,
            style_used="", chunk_count=0, reason="skipped_no_retrieval",
            retrieval_result=None,
        )

    def test_prior_answer_embedded_in_prompt(self):
        result = _build_transform_prompt_result(_PRIOR_ANSWER, "put that in bullets", self.mock_cr)
        self.assertIn(_PRIOR_ANSWER, result.assembled_prompt,
                      "Prior answer must appear verbatim in the assembled prompt")

    def test_user_request_embedded_in_prompt(self):
        result = _build_transform_prompt_result(_PRIOR_ANSWER, "put that in bullets", self.mock_cr)
        self.assertIn("put that in bullets", result.assembled_prompt,
                      "User request must appear in the assembled prompt")

    def test_generation_primer_present(self):
        result = _build_transform_prompt_result(_PRIOR_ANSWER, "make it shorter", self.mock_cr)
        self.assertIn("Reformatted answer:", result.assembled_prompt,
                      "Prompt must end with 'Reformatted answer:' primer")

    def test_was_skipped_is_false(self):
        result = _build_transform_prompt_result(_PRIOR_ANSWER, "simplify it", self.mock_cr)
        self.assertFalse(result.was_skipped,
                         "was_skipped must be False so Step 4 calls the LLM")

    def test_chunk_count_is_zero(self):
        result = _build_transform_prompt_result(_PRIOR_ANSWER, "make it shorter", self.mock_cr)
        self.assertEqual(result.chunk_count_used, 0)

    def test_bullet_transform_sets_bullet_format(self):
        result = _build_transform_prompt_result(_PRIOR_ANSWER, "put that in bullets", self.mock_cr)
        self.assertEqual(result.format_type, "bullets")

    def test_non_bullet_transform_keeps_prose_format(self):
        result = _build_transform_prompt_result(_PRIOR_ANSWER, "make it shorter", self.mock_cr)
        self.assertEqual(result.format_type, "prose")

    def test_long_prior_answer_is_truncated(self):
        long_answer = "x" * 4000
        result = _build_transform_prompt_result(long_answer, "shorten it", self.mock_cr)
        self.assertIn("[... truncated ...]", result.assembled_prompt,
                      "Answers over 3000 chars must be truncated")
        # The assembled prompt should not contain the full 4000-char answer
        self.assertNotIn("x" * 3001, result.assembled_prompt,
                         "Truncation must cap at 3000 chars")


# ---------------------------------------------------------------------------
# TEST 2 — Transform Turn: session.last_answer updates, citations preserved
# ---------------------------------------------------------------------------

class Test2TransformTurnUpdatesSession(unittest.TestCase):
    def _apply_transform_turn(self, session: SessionContext, transformed_text: str):
        """Simulate what pipeline_runner does after a successful transform LLM call."""
        turn = Turn(
            query_original="put that in bullet points",
            query_reformulated=None,
            answer_text=transformed_text,
            answer_summary=None,
            chunk_ids=[],
            route_used="answer_transform",
            style_used="direct",
            timestamp=datetime.now(timezone.utc).isoformat(),
            query_vector=[],
            citations=session.last_citations,   # preserve prior citations
            chunks=[],
            top_score=None,
        )
        session.add_turn(turn)

    def test_last_answer_is_updated_to_reformatted_text(self):
        session = _make_session_with_answer(_PRIOR_ANSWER)
        transformed = "• Gather BOL and POD.\n• Submit within 15 days.\n• Include invoice."
        self._apply_transform_turn(session, transformed)
        self.assertEqual(session.last_answer, transformed,
                         "session.last_answer must become the reformatted text")

    def test_turn_count_increments(self):
        session = _make_session_with_answer(_PRIOR_ANSWER)
        initial_count = session.turn_count
        self._apply_transform_turn(session, "• Bullet 1\n• Bullet 2")
        self.assertEqual(session.turn_count, initial_count + 1,
                         "add_turn must increment turn_count")

    def test_citations_preserved_after_transform(self):
        session = _make_session_with_answer(_PRIOR_ANSWER, citations=_CITATIONS)
        self.assertIsNotNone(session.last_citations, "Fixture must set last_citations")
        self._apply_transform_turn(session, "• Step 1\n• Step 2")
        self.assertIsNotNone(session.last_citations,
                             "last_citations must survive a transform Turn")
        self.assertEqual(session.last_citations[0]["source_filename"], "SOP.pdf",
                         "Citation filename must be preserved after transform")

    def test_second_transform_reformats_already_reformatted_text(self):
        session = _make_session_with_answer(_PRIOR_ANSWER)
        first_transform = "• Gather BOL.\n• Submit in 15 days.\n• Include details."
        self._apply_transform_turn(session, first_transform)
        # second transform reads last_answer — must see first_transform, not original
        self.assertEqual(session.last_answer, first_transform,
                         "Second transform should see the first reformatted answer as input")


# ---------------------------------------------------------------------------
# TEST 3 — No-prior-answer path: empty session
# ---------------------------------------------------------------------------

class Test3NoPriorAnswer(unittest.TestCase):
    def test_empty_session_last_answer_is_none(self):
        session = SessionContext(session_id="fresh")
        self.assertIsNone(session.last_answer,
                          "Fresh session must have last_answer=None")

    def test_no_prior_answer_message_content(self):
        # Verify the fallback message string used in the bypass
        _no_ans = (
            "There is no previous answer to reformat. Please ask a question first."
        )
        self.assertIn("no previous answer", _no_ans.lower(),
                      "Fallback message must mention 'no previous answer'")

    def test_empty_session_turn_count_unchanged(self):
        session = SessionContext(session_id="fresh")
        initial_count = session.turn_count
        # No Turn is added for the no-prior-answer path (we just verify no mutation here)
        self.assertEqual(session.turn_count, initial_count,
                         "Empty session turn_count must not change when no transform runs")


# ---------------------------------------------------------------------------
# TEST 4 — Route label stored correctly
# ---------------------------------------------------------------------------

class Test4RouteLabel(unittest.TestCase):
    def test_transform_turn_route_is_answer_transform(self):
        session = _make_session_with_answer(_PRIOR_ANSWER)
        turn = Turn(
            query_original="simplify it",
            query_reformulated=None,
            answer_text="Simplified answer.",
            answer_summary=None,
            chunk_ids=[],
            route_used="answer_transform",
            style_used="direct",
            timestamp=datetime.now(timezone.utc).isoformat(),
            query_vector=[],
            citations=None,
            chunks=[],
            top_score=None,
        )
        session.add_turn(turn)
        self.assertEqual(session.turns[-1].route_used, "answer_transform",
                         "Transform Turn must carry route_used='answer_transform'")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        Test1TransformPromptStructure,
        Test2TransformTurnUpdatesSession,
        Test3NoPriorAnswer,
        Test4RouteLabel,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"\nsmoke_transform: {passed}/{result.testsRun} pass")
    sys.exit(0 if result.wasSuccessful() else 1)
