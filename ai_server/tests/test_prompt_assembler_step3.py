#!/usr/bin/env python3
"""Deterministic unit tests for Step 3 prompt assembly."""
import sys
import tempfile
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

import ai.agents.config.agent_config_loader as loader_module
from ai.agents.models.context_mode import ContextModeResult
from ai.agents.models.domain_signal import DomainSignal
from ai.agents.models.query_understanding import QueryUnderstandingResult
from ai.agents.models.retrieval_plan import (
    PlannerRetrievalQuery,
    PlannerTask,
    RetrievalPlanResult,
)
from ai.agents.orchestrator import Group1Result
from ai.config.company_profile import load_company_profile
from ai.pipeline.prompts.format_instructions import get_format_instruction
from ai.pipeline.step1_retrieval_gate import RetrievalResult as PipelineRetrievalResult
from ai.pipeline.step2_confidence_gate import ConfidenceGateResult
from ai.pipeline.step3_prompt_assembler import run_prompt_assembler
from ai.retrieval.result_models import RetrievedChunk


def _make_group1(
    *,
    style: str = "direct",
    format_type: str = "prose",
    length_hint: str = "infer",
    query_for_retrieval: str = "What is a BOL?",
    retrieval_plan: RetrievalPlanResult | None = None,
) -> Group1Result:
    return Group1Result(
        query_original=query_for_retrieval,
        query_for_retrieval=query_for_retrieval,
        domain_signal=DomainSignal(
            domain_signal="clear_in",
            format_hint=None,
            format_is_explicit=False,
            matched_terms=["bol"],
            match_density=0.2,
            gate_decision="fast_accept",
        ),
        understanding=QueryUnderstandingResult(
            in_domain=True,
            domain_confidence="high",
            refusal_reason=None,
            style=style,
            format_type=format_type,
            format_is_explicit=False,
            length_hint=length_hint,
            classifier_method="llm",
        ),
        context_mode=ContextModeResult(
            mode="standalone",
            track="retrieval",
            requires_retrieval=True,
            requires_reformulation=False,
            prior_answer_needed=False,
            mode_confidence="high",
            mode_method="regex",
            reformulated_query=None,
        ),
        should_retrieve=True,
        should_refuse=False,
        refusal_message=None,
        style=style,
        format_type=format_type,
        length_hint=length_hint,
        total_latency_ms=12.0,
        retrieval_plan=retrieval_plan,
    )


def _make_chunk(text: str, index: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chunk-{index}",
        chunk_text=text,
        score=0.9 - (index * 0.01),
        doc_id=f"doc-{index}",
        source_filename="source.pdf",
        category="sop",
        section_heading="Section",
        page_number=index,
        access_level="internal",
        extraction_method="direct_pdf",
        upload_date="2026-04-03T00:00:00Z",
        language="en",
        chunk_index=index,
    )


def _make_confidence_result(
    *,
    passed: bool = True,
    reason: str = "passed",
    style: str = "direct",
    format_type: str = "prose",
    length_hint: str = "infer",
    query_for_retrieval: str = "What is a BOL?",
    chunks: list | None = None,
    retrieval_plan: RetrievalPlanResult | None = None,
) -> ConfidenceGateResult:
    chunks = chunks or []
    retrieval_result = PipelineRetrievalResult(
        query_used=query_for_retrieval,
        chunks=chunks,
        top_score=0.9 if chunks else 0.0,
        chunk_count=len(chunks),
        was_refused=False,
        refusal_message=None,
        was_retrieved=True,
        group1_result=_make_group1(
            style=style,
            format_type=format_type,
            length_hint=length_hint,
            query_for_retrieval=query_for_retrieval,
            retrieval_plan=retrieval_plan,
        ),
        latency_ms=10.0,
    )
    return ConfidenceGateResult(
        passed=passed,
        top_score=retrieval_result.top_score,
        threshold_used=0.4,
        style_used=style,
        chunk_count=len(chunks),
        reason=reason,
        retrieval_result=retrieval_result,
    )


def test_prompt_assembly_defaults_when_yaml_section_missing() -> None:
    yaml_text = """\
domain_gate:
  strong_in_domain_threshold: 0.15
  strong_out_domain_threshold: 0.40
  min_token_length: 3
query_understanding:
  provider: "ollama"
  model_name: "gemma3:1B"
  temperature: 0.0
  max_tokens: 200
  timeout_seconds: 90
  fallback_behavior: "default_in_domain"
context_mode:
  provider: "ollama"
  model_name: "gemma3:1B"
  temperature: 0.0
  max_tokens: 100
  timeout_seconds: 90
  fallback_behavior: "default_standalone"
reformulator:
  provider: "ollama"
  model_name: "gemma3:1B"
  temperature: 0.3
  max_tokens: 150
  timeout_seconds: 90
  fallback_behavior: "passthrough"
"""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yml",
        delete=False,
        encoding="utf-8",
    ) as handle:
        handle.write(yaml_text)
        tmp_path = Path(handle.name)

    original_path = loader_module._AGENTS_YML
    original_cache = loader_module._config_cache
    try:
        loader_module._AGENTS_YML = tmp_path
        loader_module._config_cache = None
        cfg = loader_module.load_agents_config()
        assert cfg.prompt_assembly.vocabulary_block_enabled is True
        assert cfg.prompt_assembly.max_chunks_in_prompt == 5
        assert cfg.prompt_assembly.source_header_template == "[SOURCE {n}]"
        assert cfg.prompt_assembly.default_style == "exploratory"
    finally:
        loader_module._AGENTS_YML = original_path
        loader_module._config_cache = original_cache
        tmp_path.unlink(missing_ok=True)


def test_prompt_assembler_skips_when_confidence_failed() -> None:
    confidence_result = _make_confidence_result(
        passed=False,
        reason="below_threshold",
        chunks=[_make_chunk("ignored", 1)],
    )

    result = run_prompt_assembler(confidence_result)

    assert result.was_skipped is True
    assert result.skip_reason == "below_threshold"
    assert result.assembled_prompt == ""
    assert result.system_prompt == ""
    assert result.format_instruction == ""
    assert result.chunk_count_used == 0
    assert result.style_used == ""


def test_prompt_assembler_falls_back_to_exploratory_and_orders_sections() -> None:
    confidence_result = _make_confidence_result(
        style="not-a-real-style",
        format_type="prose",
        length_hint="infer",
        query_for_retrieval="Explain return authorizations.",
        chunks=[_make_chunk("First chunk text", 1), _make_chunk("Second chunk text", 2)],
    )

    result = run_prompt_assembler(confidence_result)

    assert result.was_skipped is False
    assert result.style_used == "exploratory"
    assert result.system_prompt.startswith("You are an evidence-controlled answer composer for")
    assert not result.assembled_prompt.startswith("You are an evidence-controlled")
    assert result.system_prompt not in result.assembled_prompt
    assert "--- DOMAIN TERMINOLOGY ---" not in result.assembled_prompt
    first_abbreviation = load_company_profile().domain.abbreviations[0]
    assert first_abbreviation not in result.assembled_prompt
    assert "[SOURCE 1]\nFirst chunk text" in result.assembled_prompt
    assert "QUESTION: Explain return authorizations." in result.assembled_prompt

    format_idx = result.assembled_prompt.index("--- FORMAT INSTRUCTION ---")
    sources_idx = result.assembled_prompt.index("--- SOURCE DOCUMENTS ---")
    question_idx = result.assembled_prompt.index("QUESTION: Explain return authorizations.")

    assert format_idx < sources_idx < question_idx


def test_prompt_assembler_uses_default_instruction_for_medium_and_caps_chunks() -> None:
    chunks = [_make_chunk(f"Chunk text {i}", i) for i in range(1, 13)]
    confidence_result = _make_confidence_result(
        style="direct",
        format_type="bullets",
        length_hint="medium",
        query_for_retrieval="List claim details.",
        chunks=chunks,
    )

    result = run_prompt_assembler(confidence_result)

    assert result.was_skipped is False
    assert result.chunk_count_used == 10
    assert result.format_instruction == get_format_instruction("bullets", "medium")
    assert "[SOURCE 10]\nChunk text 10" in result.assembled_prompt
    assert "[SOURCE 11]" not in result.assembled_prompt
    assert "Chunk text 11" not in result.assembled_prompt


def test_prompt_assembler_supports_fallback_chunk_content_field() -> None:
    class ContentChunk:
        def __init__(self, content: str):
            self.content = content

    confidence_result = _make_confidence_result(
        style="direct",
        format_type="concise",
        length_hint="short",
        query_for_retrieval="What is POD?",
        chunks=[ContentChunk("Content fallback chunk")],
    )

    result = run_prompt_assembler(confidence_result)

    assert result.was_skipped is False
    assert "Content fallback chunk" in result.assembled_prompt
    assert result.format_instruction == get_format_instruction("concise", "short")


def test_prompt_assembler_includes_retrieval_planner_context() -> None:
    retrieval_plan = RetrievalPlanResult(
        case_context_present=True,
        case_facts=["Load ID / BOL: 17847773", "Carrier: CH Robinson"],
        tasks=[
            PlannerTask(
                id="task_1",
                task_text="List required notifications",
                evidence_needed=["SOP-02 notification requirements"],
            )
        ],
        retrieval_queries=[
            PlannerRetrievalQuery(
                id="q1",
                task_ids=["task_1"],
                query="SOP-02 theft incident required notifications",
                priority="high",
            )
        ],
        preserve_for_answer=["Load ID / BOL: 17847773"],
        answer_constraints=["Do not cite user-provided case facts as source evidence"],
        planner_method="llm",
    )
    confidence_result = _make_confidence_result(
        style="procedural",
        format_type="numbered_list",
        query_for_retrieval="case prompt",
        chunks=[_make_chunk("SOP evidence chunk", 1)],
        retrieval_plan=retrieval_plan,
    )

    result = run_prompt_assembler(confidence_result)

    assert result.was_skipped is False
    assert "--- USER CASE FACTS ---" in result.assembled_prompt
    assert "- Load ID / BOL: 17847773" in result.assembled_prompt
    assert "--- USER TASKS ---" in result.assembled_prompt
    assert "task_1: List required notifications" in result.assembled_prompt
    assert "--- PRESERVE FOR ANSWER ---" in result.assembled_prompt
    assert "--- GROUNDING CONSTRAINTS ---" in result.assembled_prompt
    assert "Use USER CASE FACTS only as facts supplied by the user." in result.assembled_prompt
    assert "[SOURCE 1]\nSOP evidence chunk" in result.assembled_prompt


def test_prompt_assembler_includes_available_source_filenames_section() -> None:
    chunks = [
        _make_chunk("First chunk", 1),
        _make_chunk("Second chunk", 2),
        _make_chunk("Third chunk", 3),
    ]
    confidence_result = _make_confidence_result(
        style="direct",
        format_type="prose",
        length_hint="infer",
        query_for_retrieval="What is a BOL?",
        chunks=chunks,
    )

    result = run_prompt_assembler(confidence_result)

    assert "--- AVAILABLE SOURCE FILENAMES ---" in result.assembled_prompt
    assert "--- END SOURCE FILENAMES ---" in result.assembled_prompt
    # _make_chunk gives every chunk source_filename="source.pdf", so dedup
    # should produce exactly one entry.
    assert result.assembled_prompt.count("- source.pdf") == 1

    # Ordering: AVAILABLE SOURCE FILENAMES sits between SOURCE DOCUMENTS and QUESTION.
    sources_idx = result.assembled_prompt.index("--- SOURCE DOCUMENTS ---")
    filenames_idx = result.assembled_prompt.index("--- AVAILABLE SOURCE FILENAMES ---")
    question_idx = result.assembled_prompt.index("QUESTION: What is a BOL?")
    assert sources_idx < filenames_idx < question_idx


def test_prompt_assembler_dedupes_and_orders_filenames() -> None:
    class NamedChunk:
        def __init__(self, text: str, filename: str):
            self.chunk_text = text
            self.source_filename = filename

    chunks = [
        NamedChunk("alpha text", "alpha.pdf"),
        NamedChunk("beta text", "beta.pdf"),
        NamedChunk("alpha again", "alpha.pdf"),
        NamedChunk("gamma text", "gamma.pdf"),
    ]
    confidence_result = _make_confidence_result(
        style="direct",
        format_type="prose",
        length_hint="infer",
        query_for_retrieval="Test dedup.",
        chunks=chunks,
    )

    result = run_prompt_assembler(confidence_result)

    assert result.assembled_prompt.count("- alpha.pdf") == 1
    assert result.assembled_prompt.count("- beta.pdf") == 1
    assert result.assembled_prompt.count("- gamma.pdf") == 1

    # First-seen order is preserved.
    alpha_idx = result.assembled_prompt.index("- alpha.pdf")
    beta_idx = result.assembled_prompt.index("- beta.pdf")
    gamma_idx = result.assembled_prompt.index("- gamma.pdf")
    assert alpha_idx < beta_idx < gamma_idx


if __name__ == "__main__":
    tests = [
        test_prompt_assembly_defaults_when_yaml_section_missing,
        test_prompt_assembler_skips_when_confidence_failed,
        test_prompt_assembler_falls_back_to_exploratory_and_orders_sections,
        test_prompt_assembler_uses_default_instruction_for_medium_and_caps_chunks,
        test_prompt_assembler_supports_fallback_chunk_content_field,
        test_prompt_assembler_includes_retrieval_planner_context,
        test_prompt_assembler_includes_available_source_filenames_section,
        test_prompt_assembler_dedupes_and_orders_filenames,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  PASS  {test_fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test_fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
