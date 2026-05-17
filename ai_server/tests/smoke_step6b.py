"""
Smoke tests for Step 6b - Stage 2 citation_lookup detection.

No Redis, Qdrant, or Ollama required.

Run:
    python tests/smoke_step6b.py
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


# Resolve project root so imports work regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai.agents.orchestrator as orchestrator_module
import ai.agents.stage2_context_mode as context_mode_module
from ai.agents.config.agent_config_schema import LLMConfig
from ai.agents.models.context_mode import ContextModeResult
from ai.agents.models.domain_signal import DomainSignal
from ai.agents.models.query_understanding import QueryUnderstandingResult
from ai.agents.models.session import SessionContext, Turn


_CITATIONS = [
    {
        "rank": 1,
        "source_filename": "SOP.pdf",
        "page_number": 4,
        "section_heading": "3.2 Shortage Claims",
        "score_pct": 91,
        "category": "sop",
        "extraction_method": "text_extraction",
        "upload_date": None,
        "chunk_indices": [3],
    }
]


def _config() -> LLMConfig:
    return LLMConfig(
        provider="ollama",
        model_name="unused",
        temperature=0.0,
        max_tokens=100,
        timeout_seconds=1,
        fallback_behavior="default_standalone",
    )


def _understanding() -> QueryUnderstandingResult:
    return QueryUnderstandingResult(
        in_domain=True,
        domain_confidence="high",
        refusal_reason=None,
        style="direct",
        format_type="prose",
        format_is_explicit=False,
        length_hint="infer",
        classifier_method="test",
    )


def _turn() -> Turn:
    return Turn(
        query_original="What are the steps to file a shortage claim?",
        query_reformulated=None,
        answer_text="To file a shortage claim, review the deduction and gather support.",
        answer_summary=None,
        chunk_ids=["chunk-001"],
        route_used="sop",
        style_used="procedural",
        timestamp="2026-04-12T10:00:00Z",
        query_vector=None,
        citations=_CITATIONS,
    )


def _session(citations: list[dict] | None = _CITATIONS) -> SessionContext:
    return SessionContext(
        session_id="sess-step6b",
        turns=[_turn()],
        turn_count=1,
        last_citations=citations,
    )


def _llm_citation_lookup(*args, **kwargs) -> str:
    return """{
  "mode": "citation_lookup",
  "confidence": "high",
  "reasoning": "The user asks where the prior answer came from."
}"""


class TestStage2CitationLookup(unittest.TestCase):
    def test_regex_detects_page_lookup(self) -> None:
        result = context_mode_module.run_stage2(
            "what page was that on?",
            _understanding(),
            _session(),
            _config(),
        )

        self.assertEqual(result.mode, "citation_lookup")
        self.assertEqual(result.track, "citation")
        self.assertFalse(result.requires_retrieval)
        self.assertFalse(result.requires_reformulation)
        self.assertEqual(result.mode_confidence, "high")
        self.assertEqual(result.mode_method, "regex")

    def test_regex_detects_section_lookup(self) -> None:
        result = context_mode_module.run_stage2(
            "which section covered that?",
            _understanding(),
            _session(),
            _config(),
        )

        self.assertEqual(result.mode, "citation_lookup")
        self.assertEqual(result.track, "citation")
        self.assertFalse(result.requires_retrieval)

    def test_regex_guard_blocks_none_citations(self) -> None:
        regex_result = context_mode_module._classify_by_patterns(
            "what page was that on?",
            _session(citations=None),
        )

        self.assertNotEqual(
            regex_result[0] if regex_result is not None else None,
            "citation_lookup",
        )

    def test_regex_guard_blocks_empty_citations(self) -> None:
        regex_result = context_mode_module._classify_by_patterns(
            "which document was that from?",
            _session(citations=[]),
        )

        self.assertNotEqual(
            regex_result[0] if regex_result is not None else None,
            "citation_lookup",
        )

    def test_normal_followup_not_caught(self) -> None:
        result = context_mode_module.run_stage2(
            "what about the timeline?",
            _understanding(),
            _session(),
            _config(),
        )

        self.assertEqual(result.mode, "retrieval_followup")
        self.assertEqual(result.track, "retrieval")

    def test_answer_transform_not_caught(self) -> None:
        result = context_mode_module.run_stage2(
            "put that in bullet points",
            _understanding(),
            _session(),
            _config(),
        )

        self.assertEqual(result.mode, "answer_transform")
        self.assertEqual(result.track, "transform")

    def test_where_can_i_find_that_is_caught(self) -> None:
        result = context_mode_module.run_stage2(
            "where can I find that in the document?",
            _understanding(),
            _session(),
            _config(),
        )

        self.assertEqual(result.mode, "citation_lookup")
        self.assertEqual(result.track, "citation")
        self.assertFalse(result.requires_retrieval)

    def test_llm_can_return_citation_lookup(self) -> None:
        with patch.object(context_mode_module, "_call_ollama_generate", _llm_citation_lookup):
            result = context_mode_module.run_stage2(
                "can you point me back",
                _understanding(),
                _session(),
                _config(),
            )

        self.assertEqual(result.mode, "citation_lookup")
        self.assertEqual(result.track, "citation")
        self.assertFalse(result.requires_retrieval)
        self.assertEqual(result.mode_method, "llm")

    def test_llm_citation_lookup_guard_requires_citations(self) -> None:
        with patch.object(context_mode_module, "_call_ollama_generate", _llm_citation_lookup):
            result = context_mode_module.run_stage2(
                "can you point me back",
                _understanding(),
                _session(citations=[]),
                _config(),
            )

        self.assertEqual(result.mode, "standalone")
        self.assertEqual(result.track, "retrieval")
        self.assertTrue(result.requires_retrieval)
        self.assertEqual(result.mode_method, "fallback_standalone")


class TestOrchestratorCitationLookup(unittest.TestCase):
    def test_orchestrator_sets_should_retrieve_false(self) -> None:
        cfg = SimpleNamespace(
            domain_gate=object(),
            query_understanding=object(),
            context_mode=object(),
            reformulator=object(),
        )

        domain_signal = DomainSignal(
            domain_signal="clear_in",
            format_hint=None,
            format_is_explicit=False,
            matched_terms=["claim"],
            match_density=0.2,
            gate_decision="fast_accept",
        )

        context_mode = ContextModeResult(
            mode="citation_lookup",
            track="citation",
            requires_retrieval=False,
            requires_reformulation=False,
            prior_answer_needed=False,
            mode_confidence="high",
            mode_method="regex",
            reformulated_query=None,
        )

        with (
            patch.object(orchestrator_module, "load_agents_config", return_value=cfg),
            patch.object(orchestrator_module, "run_stage0", return_value=domain_signal),
            patch.object(orchestrator_module, "run_stage1", return_value=_understanding()),
            patch.object(orchestrator_module, "run_stage2", return_value=context_mode),
            patch.object(
                orchestrator_module,
                "run_stage2a",
                side_effect=AssertionError("Stage 2a must not run for citation_lookup"),
            ),
        ):
            result = orchestrator_module.run_group1(
                "what page was that on?",
                _session(),
            )

        self.assertEqual(result.context_mode.mode, "citation_lookup")
        self.assertFalse(result.should_retrieve)
        self.assertFalse(result.should_refuse)
        self.assertEqual(result.query_for_retrieval, "what page was that on?")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("smoke_step6b - Stage 2 citation_lookup detection")
    print("=" * 60)
    unittest.main(verbosity=2)
