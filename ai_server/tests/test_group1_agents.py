#!/usr/bin/env python3
"""Smoke tests for Group 1 agent orchestration foundations and LLM helpers.

Pytest-compatible - run with:
    cd ai_server
    python -m pytest tests/test_group1_agents.py -v

Standalone (no pytest required):
    cd ai_server
    python tests/test_group1_agents.py

No running services required. All LLM interactions are monkeypatched locally.
"""
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

# Allow standalone execution from any working directory
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

import ai.agents.stage1_query_understanding as query_understanding_module
import ai.agents.stage2_context_mode as context_mode_module
import ai.agents.stage2a_reformulator as reformulator_module
from ai.agents.config.agent_config_loader import load_agents_config
from ai.agents.config.agent_config_schema import AgentsConfig
from ai.agents.models.context_mode import ContextModeResult
from ai.agents.models.query_understanding import QueryUnderstandingResult
from ai.agents.models.session import SessionContext, Turn
from ai.agents.stage0_domain_gate import run_stage0
from ai.agents.orchestrator import run_group1, Group1Result
from ai.config.company_profile import load_company_profile


@contextmanager
def _patched_attr(obj, attr_name: str, replacement):
    original = getattr(obj, attr_name)
    setattr(obj, attr_name, replacement)
    try:
        yield
    finally:
        setattr(obj, attr_name, original)


def _dummy_understanding() -> QueryUnderstandingResult:
    return QueryUnderstandingResult(
        in_domain=True,
        domain_confidence="high",
        refusal_reason=None,
        style="direct",
        format_type="prose",
        format_is_explicit=False,
        length_hint="infer",
        classifier_method="llm",
    )


def _make_session(
    query_original: str,
    answer_text: str,
    *,
    route_used: str = "procedure",
    style_used: str = "procedural",
) -> SessionContext:
    turn = Turn(
        query_original=query_original,
        query_reformulated=None,
        answer_text=answer_text,
        answer_summary=None,
        chunk_ids=["chunk-001"],
        route_used=route_used,
        style_used=style_used,
        timestamp="2026-03-30T10:00:00Z",
        query_vector=None,
    )
    return SessionContext(session_id="sess-001", turns=[turn], turn_count=1)


def _raise_model_error(*args, **kwargs):
    raise RuntimeError("simulated model failure")


# ---------------------------------------------------------------------------
# 1. Config loads from YAML
# ---------------------------------------------------------------------------

def test_config_loads() -> None:
    cfg = load_agents_config()
    assert isinstance(cfg, AgentsConfig)
    assert cfg.domain_gate.strong_in_domain_threshold == 0.15
    assert cfg.domain_gate.strong_out_domain_threshold == 0.40
    assert cfg.domain_gate.min_token_length == 3
    assert cfg.query_understanding.provider == "ollama"
    assert cfg.query_understanding.model_name == "llama3.1:8b"
    assert cfg.context_mode.fallback_behavior == "default_standalone"
    assert cfg.reformulator.temperature == 0.3
    assert cfg.retrieval_planner.model_name == cfg.query_understanding.model_name
    assert cfg.retrieval_planner.temperature == 0.0
    assert cfg.retrieval_planner.fallback_behavior == "passthrough_single_query"
    assert cfg.prompt_assembly.vocabulary_block_enabled is False
    assert cfg.prompt_assembly.max_chunks_in_prompt == 10
    assert cfg.prompt_assembly.default_style == "exploratory"
    assert cfg.prompt_assembly.source_header_template == "[SOURCE {n}]"
    profile = load_company_profile()
    assert len(profile.domain.abbreviations) > 0


# ---------------------------------------------------------------------------
# 2. Missing YAML raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_missing_yaml_raises_file_not_found() -> None:
    import ai.agents.config.agent_config_loader as loader_module

    original_path = loader_module._AGENTS_YML
    original_cache = loader_module._config_cache
    try:
        loader_module._AGENTS_YML = Path("/nonexistent/path/agents.yml")
        loader_module._config_cache = None
        raised = False
        try:
            loader_module.load_agents_config()
        except FileNotFoundError:
            raised = True
        assert raised, "Expected FileNotFoundError when agents.yml is missing"
    finally:
        loader_module._AGENTS_YML = original_path
        loader_module._config_cache = original_cache


# ---------------------------------------------------------------------------
# 3. Missing required field raises KeyError with the field name
# ---------------------------------------------------------------------------

def test_missing_field_raises_key_error() -> None:
    import ai.agents.config.agent_config_loader as loader_module

    bad_yaml = """\
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
  # fallback_behavior intentionally absent
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
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(bad_yaml)
        tmp_path = Path(handle.name)

    original_path = loader_module._AGENTS_YML
    original_cache = loader_module._config_cache
    try:
        loader_module._AGENTS_YML = tmp_path
        loader_module._config_cache = None
        raised = False
        missing_key = None
        try:
            loader_module.load_agents_config()
        except KeyError as exc:
            raised = True
            missing_key = exc.args[0]
        assert raised, "Expected KeyError when required field is absent"
        assert missing_key == "fallback_behavior", (
            f"Expected missing key 'fallback_behavior', got {missing_key!r}"
        )
    finally:
        loader_module._AGENTS_YML = original_path
        loader_module._config_cache = original_cache
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 4. Freight shortage claim -> clear_in + format_hint=steps
# ---------------------------------------------------------------------------

def test_freight_shortage_claim_clear_in_steps() -> None:
    cfg = load_agents_config()
    query = "What are the steps to process a freight shortage claim?"
    result = run_stage0(query, cfg.domain_gate)
    assert result.domain_signal == "clear_in", (
        f"Expected clear_in, got {result.domain_signal!r}. "
        f"matched={result.matched_terms}, density={result.match_density:.3f}"
    )
    assert result.gate_decision == "fast_accept"
    assert result.format_hint == "steps", (
        f"Expected format_hint='steps', got {result.format_hint!r}"
    )
    assert result.format_is_explicit is True


# ---------------------------------------------------------------------------
# 5. Out-of-domain political question -> clear_out
# ---------------------------------------------------------------------------

def test_out_of_domain_clear_out() -> None:
    cfg = load_agents_config()
    query = "Who is the president of the United States?"
    result = run_stage0(query, cfg.domain_gate)
    assert result.domain_signal == "clear_out", (
        f"Expected clear_out, got {result.domain_signal!r}. "
        f"matched={result.matched_terms}"
    )
    assert result.gate_decision == "fast_reject"


# ---------------------------------------------------------------------------
# 6. Return authorization bullet list -> bullets format, explicit=True
# ---------------------------------------------------------------------------

def test_return_authorization_bullets() -> None:
    cfg = load_agents_config()
    query = "List the documents required for a return authorization in bullet points"
    result = run_stage0(query, cfg.domain_gate)
    assert result.format_hint == "bullets", (
        f"Expected format_hint='bullets', got {result.format_hint!r}"
    )
    assert result.format_is_explicit is True
    assert result.domain_signal in ("clear_in", "borderline"), (
        f"Expected clear_in or borderline, got {result.domain_signal!r}. "
        f"matched={result.matched_terms}, density={result.match_density:.3f}"
    )


# ---------------------------------------------------------------------------
# 7. Creative request with generic domain term -> borderline, not fast_accept
# ---------------------------------------------------------------------------

def test_creative_request_with_generic_domain_term_is_borderline() -> None:
    cfg = load_agents_config()
    query = "Write me a poem about logistics"
    result = run_stage0(query, cfg.domain_gate)
    assert result.domain_signal == "borderline", (
        f"Expected borderline, got {result.domain_signal!r}. "
        f"matched={result.matched_terms}, density={result.match_density:.3f}"
    )
    assert result.gate_decision == "escalate_to_llm"
    assert result.matched_terms == ["logistics"]


# ---------------------------------------------------------------------------
# 8. Generic single-word logistics query -> borderline, not fast_accept
# ---------------------------------------------------------------------------

def test_generic_domain_word_is_borderline() -> None:
    cfg = load_agents_config()
    query = "What is a carrier?"
    result = run_stage0(query, cfg.domain_gate)
    assert result.domain_signal == "borderline", (
        f"Expected borderline, got {result.domain_signal!r}. "
        f"matched={result.matched_terms}, density={result.match_density:.3f}"
    )
    assert result.gate_decision == "escalate_to_llm"
    assert result.matched_terms == ["carrier"]


# ---------------------------------------------------------------------------
# 9. Returned shipment with configured customer mention -> clear_in via high-signal entity
# ---------------------------------------------------------------------------

def test_returned_shipment_from_configured_customer_is_clear_in() -> None:
    cfg = load_agents_config()
    customer_name = load_company_profile().domain.customers[0]
    query = f"What is the procedure for handling a returned shipment from {customer_name}?"
    result = run_stage0(query, cfg.domain_gate)
    assert result.domain_signal == "clear_in", (
        f"Expected clear_in, got {result.domain_signal!r}. "
        f"matched={result.matched_terms}, density={result.match_density:.3f}"
    )
    assert result.gate_decision == "fast_accept"
    assert customer_name in result.matched_terms


# ---------------------------------------------------------------------------
# 10. SessionContext convenience properties - non-empty turns
# ---------------------------------------------------------------------------

def test_session_context_properties_non_empty() -> None:
    turn = Turn(
        query_original="What is the claim process?",
        query_reformulated=None,
        answer_text="The claim process involves three steps.",
        answer_summary=None,
        chunk_ids=["chunk-001", "chunk-002"],
        route_used="sop",
        style_used="procedural",
        timestamp="2026-03-30T10:00:00Z",
        query_vector=None,
    )
    session = SessionContext(session_id="sess-001", turns=[turn], turn_count=1)

    assert session.last_query == "What is the claim process?"
    assert session.last_answer == "The claim process involves three steps."
    assert session.last_chunks == ["chunk-001", "chunk-002"]
    assert session.last_route == "sop"


# ---------------------------------------------------------------------------
# 11. SessionContext convenience properties - empty turns
# ---------------------------------------------------------------------------

def test_session_context_properties_empty() -> None:
    session = SessionContext(session_id="sess-empty")
    assert session.last_query is None
    assert session.last_answer is None
    assert session.last_chunks == []
    assert session.last_route is None


# ---------------------------------------------------------------------------
# 12. Query understanding -> in-domain procedural classification
# ---------------------------------------------------------------------------

def test_query_understanding_procedural_in_domain() -> None:
    cfg = load_agents_config()
    query = "What are the steps to process a freight shortage claim?"
    domain_signal = run_stage0(query, cfg.domain_gate)

    def fake_generate(*args, **kwargs):
        return """{
  "in_domain": true,
  "domain_confidence": "high",
  "refusal_reason": null,
  "style": "procedural",
  "format_type": "prose",
  "format_is_explicit": false,
  "length_hint": "infer"
}"""

    with _patched_attr(query_understanding_module, "_call_ollama_generate", fake_generate):
        result = query_understanding_module.run_stage1(
            query,
            domain_signal,
            cfg.query_understanding,
        )

    assert result.in_domain is True
    assert result.style == "procedural"
    assert result.format_type == "numbered_list"
    assert result.format_is_explicit is True
    assert result.classifier_method == "llm"


# ---------------------------------------------------------------------------
# 13. Query understanding -> skip clear_out without model call
# ---------------------------------------------------------------------------

def test_query_understanding_skips_clear_out() -> None:
    cfg = load_agents_config()
    query = "Who is the president of the United States?"
    domain_signal = run_stage0(query, cfg.domain_gate)

    with _patched_attr(query_understanding_module, "_call_ollama_generate", _raise_model_error):
        result = query_understanding_module.run_stage1(
            query,
            domain_signal,
            cfg.query_understanding,
        )

    assert result.in_domain is False
    assert result.domain_confidence == "high"
    assert result.refusal_reason == (
        "Query does not appear to relate to company documents or operations."
    )
    assert result.classifier_method == "skipped_clear_out"


# ---------------------------------------------------------------------------
# 14. Query understanding -> explicit bullets override is preserved
# ---------------------------------------------------------------------------

def test_query_understanding_preserves_explicit_bullets() -> None:
    cfg = load_agents_config()
    query = "List the documents required for a return authorization in bullet points"
    domain_signal = run_stage0(query, cfg.domain_gate)

    def fake_generate(*args, **kwargs):
        return """{
  "in_domain": true,
  "domain_confidence": "medium",
  "refusal_reason": null,
  "style": "direct",
  "format_type": "prose",
  "format_is_explicit": false,
  "length_hint": "infer"
}"""

    with _patched_attr(query_understanding_module, "_call_ollama_generate", fake_generate):
        result = query_understanding_module.run_stage1(
            query,
            domain_signal,
            cfg.query_understanding,
        )

    assert result.in_domain is True
    assert result.format_type == "bullets"
    assert result.format_is_explicit is True


# ---------------------------------------------------------------------------
# 15. Query understanding -> model failure fallback
# ---------------------------------------------------------------------------

def test_query_understanding_failure_fallback() -> None:
    cfg = load_agents_config()
    query = "What are the steps to process a freight shortage claim?"
    domain_signal = run_stage0(query, cfg.domain_gate)

    with _patched_attr(query_understanding_module, "_call_ollama_generate", _raise_model_error):
        result = query_understanding_module.run_stage1(
            query,
            domain_signal,
            cfg.query_understanding,
        )

    assert result.in_domain is True
    assert result.domain_confidence == "low"
    assert result.style == "direct"
    assert result.format_type == "numbered_list"
    assert result.format_is_explicit is True
    assert result.classifier_method == "fallback_default"


# ---------------------------------------------------------------------------
# 16. Context mode -> explicit answer transform
# ---------------------------------------------------------------------------

def test_context_mode_answer_transform() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What are the steps to process a freight shortage claim?",
        "A prior answer about the shortage process.",
    )
    result = context_mode_module.run_stage2(
        "Make it shorter",
        _dummy_understanding(),
        session,
        cfg.context_mode,
    )

    assert result.mode == "answer_transform"
    assert result.track == "transform"
    assert result.requires_retrieval is False
    assert result.prior_answer_needed is True
    assert result.mode_method == "regex"


# ---------------------------------------------------------------------------
# 17. Context mode -> retrieval follow-up for vague continuation
# ---------------------------------------------------------------------------

def test_context_mode_retrieval_followup() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What are the steps to process a freight shortage claim?",
        "The analyst reviews the deduction, notifies SEACLAIMS, and proceeds after RA approval.",
    )
    result = context_mode_module.run_stage2(
        "what about the timeline?",
        _dummy_understanding(),
        session,
        cfg.context_mode,
    )

    assert result.mode == "retrieval_followup"
    assert result.track == "retrieval"
    assert result.requires_retrieval is True
    assert result.requires_reformulation is True
    assert result.mode_method == "regex"


# ---------------------------------------------------------------------------
# 18. Context mode -> correction challenge is retrieval follow-up
# ---------------------------------------------------------------------------

def test_context_mode_correction_challenge_followup() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "When is the first mail date for claim reference 3291474811?",
        "The first mail date is August 25, 2025.",
        route_used="direct",
        style_used="direct",
    )
    result = context_mode_module.run_stage2(
        "isn't it 12th August?",
        _dummy_understanding(),
        session,
        cfg.context_mode,
    )

    assert result.mode == "retrieval_followup"
    assert result.track == "retrieval"
    assert result.requires_reformulation is True
    assert result.mode_method == "regex"


# ---------------------------------------------------------------------------
# 19. Context mode -> correction detector ignores plain reformat preface
# ---------------------------------------------------------------------------

def test_correction_detector_ignores_plain_reformat_preface() -> None:
    assert context_mode_module.is_correction_challenge("actually make it shorter") is False
    assert context_mode_module.is_correction_challenge("actually it was closed") is True


# ---------------------------------------------------------------------------
# 20. Context mode -> standalone despite prior session
# ---------------------------------------------------------------------------

def test_context_mode_standalone_new_question() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What is a BOL?",
        "A BOL is a carrier-issued shipping document.",
        route_used="direct",
        style_used="direct",
    )
    result = context_mode_module.run_stage2(
        "What is the procedure for handling a returned shipment from Amazon?",
        _dummy_understanding(),
        session,
        cfg.context_mode,
    )

    assert result.mode == "standalone"
    assert result.track == "retrieval"
    assert result.requires_retrieval is True
    assert result.requires_reformulation is False
    assert result.mode_method == "regex"


# ---------------------------------------------------------------------------
# 21. Context mode -> case-study prompt is standalone despite prior session
# ---------------------------------------------------------------------------

def test_context_mode_case_study_prompt_is_standalone_despite_prior_session() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What is the RPOD request process?",
        "A prior answer about requesting RPOD from a carrier.",
        route_used="procedure",
        style_used="procedural",
    )
    query = (
        'Katherine Kim requested RPOD from UNIS for: - DO: 7256988348 '
        '- Load/Pro: 17620449 - Carrier Response: "Hello. Please proceed with claims." '
        "The carrier has confirmed the freight is lost. Per SOP-11: "
        "1. Confirm this triggers immediate claim filing against the carrier "
        "2. Generate the claim filing package "
        "3. Calculate the Carrier Response SLA compliance "
        '4. Update the RA tracking to reflect "Claim Filed" status'
    )

    result = context_mode_module.run_stage2(
        query,
        _dummy_understanding(),
        session,
        cfg.context_mode,
    )

    assert result.mode == "standalone"
    assert result.track == "retrieval"
    assert result.requires_retrieval is True
    assert result.requires_reformulation is False
    assert result.mode_method == "regex"


# ---------------------------------------------------------------------------
# 22. Context mode -> transform override when domain term is present
# ---------------------------------------------------------------------------

def test_context_mode_transform_override_to_followup() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What documents are needed for claims?",
        "You need a signed POD, Debit Memo, invoice details, and BOL/Load ID.",
        route_used="direct",
        style_used="direct",
    )
    result = context_mode_module.run_stage2(
        "summarize the RA process",
        _dummy_understanding(),
        session,
        cfg.context_mode,
    )

    assert result.mode == "retrieval_followup"
    assert result.track == "retrieval"
    assert result.requires_reformulation is True
    assert result.mode_method == "regex"


# ---------------------------------------------------------------------------
# 23. Context mode -> model fallback when regex is uncertain
# ---------------------------------------------------------------------------

def test_context_mode_failure_fallback() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What are the steps to process a freight shortage claim?",
        "A prior answer about the shortage process.",
    )

    with _patched_attr(context_mode_module, "_call_ollama_generate", _raise_model_error):
        result = context_mode_module.run_stage2(
            "Need help",
            _dummy_understanding(),
            session,
            cfg.context_mode,
        )

    assert result.mode == "standalone"
    assert result.track == "retrieval"
    assert result.requires_retrieval is True
    assert result.requires_reformulation is False
    assert result.mode_confidence == "low"
    assert result.mode_method == "fallback_standalone"


# ---------------------------------------------------------------------------
# 24. Context mode -> model path succeeds when regex is uncertain
# ---------------------------------------------------------------------------

def test_context_mode_llm_success() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What are the steps to process a freight shortage claim?",
        "A prior answer about the shortage process.",
    )

    def fake_generate(*args, **kwargs):
        return """{
  "mode": "retrieval_followup",
  "confidence": "medium",
  "reasoning": "The user wants more detail on the same topic."
}"""

    with _patched_attr(context_mode_module, "_call_ollama_generate", fake_generate):
        result = context_mode_module.run_stage2(
            "clarify the approval path",
            _dummy_understanding(),
            session,
            cfg.context_mode,
        )

    assert result.mode == "retrieval_followup"
    assert result.track == "retrieval"
    assert result.requires_reformulation is True
    assert result.mode_confidence == "medium"
    assert result.mode_method == "llm"


# ---------------------------------------------------------------------------
# 25. Reformulator -> vague follow-up becomes standalone query
# ---------------------------------------------------------------------------

def test_reformulator_rewrites_followup() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "How do I process a return authorization?",
        "The answer described the RA workflow.",
    )
    context_mode = ContextModeResult(
        mode="retrieval_followup",
        track="retrieval",
        requires_retrieval=True,
        requires_reformulation=True,
        prior_answer_needed=False,
        mode_confidence="high",
        mode_method="regex",
        reformulated_query=None,
    )

    def fake_rewrite(*args, **kwargs):
        return '"What is the timeline for processing a return authorization?"'

    with _patched_attr(reformulator_module, "_rewrite_followup_query", fake_rewrite):
        result = reformulator_module.run_stage2a(
            "and the timeline?",
            context_mode,
            session,
            cfg.reformulator,
        )

    assert result == "What is the timeline for processing a return authorization?"
    assert context_mode.reformulated_query == result


# ---------------------------------------------------------------------------
# 26. Reformulator -> correction challenge preserves candidate value
# ---------------------------------------------------------------------------

def test_reformulator_preserves_correction_challenge_without_llm() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "When is the first mail date for claim reference 3291474811?",
        "The first mail date is August 25, 2025.",
        route_used="direct",
        style_used="direct",
    )
    context_mode = ContextModeResult(
        mode="retrieval_followup",
        track="retrieval",
        requires_retrieval=True,
        requires_reformulation=True,
        prior_answer_needed=False,
        mode_confidence="high",
        mode_method="regex",
        reformulated_query=None,
    )

    with _patched_attr(reformulator_module, "_rewrite_followup_query", _raise_model_error):
        result = reformulator_module.run_stage2a(
            "isn't it 12th August?",
            context_mode,
            session,
            cfg.reformulator,
        )

    assert "3291474811" in result
    assert "12th August" in result
    assert "proposed correction" in result
    assert context_mode.reformulated_query == result


# ---------------------------------------------------------------------------
# 27. Reformulator -> model failure falls back to passthrough
# ---------------------------------------------------------------------------

def test_reformulator_failure_passthrough() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "How do I process a return authorization?",
        "The answer described the RA workflow.",
    )
    context_mode = ContextModeResult(
        mode="retrieval_followup",
        track="retrieval",
        requires_retrieval=True,
        requires_reformulation=True,
        prior_answer_needed=False,
        mode_confidence="high",
        mode_method="regex",
        reformulated_query=None,
    )

    with _patched_attr(reformulator_module, "_rewrite_followup_query", _raise_model_error):
        result = reformulator_module.run_stage2a(
            "and the timeline?",
            context_mode,
            session,
            cfg.reformulator,
        )

    assert result == "and the timeline?"
    assert context_mode.reformulated_query == "and the timeline?"


# ---------------------------------------------------------------------------
# 25. Reformulator -> invalid short output falls back to passthrough
# ---------------------------------------------------------------------------

def test_reformulator_invalid_short_output_passthrough() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "How do I process a return authorization?",
        "The answer described the RA workflow.",
    )
    context_mode = ContextModeResult(
        mode="retrieval_followup",
        track="retrieval",
        requires_retrieval=True,
        requires_reformulation=True,
        prior_answer_needed=False,
        mode_confidence="high",
        mode_method="regex",
        reformulated_query=None,
    )

    def fake_rewrite(*args, **kwargs):
        return "timeline?"

    with _patched_attr(reformulator_module, "_rewrite_followup_query", fake_rewrite):
        result = reformulator_module.run_stage2a(
            "and the timeline?",
            context_mode,
            session,
            cfg.reformulator,
        )

    assert result == "and the timeline?"
    assert context_mode.reformulated_query == "and the timeline?"


# ---------------------------------------------------------------------------
# 26. Reformulator -> self-contained case prompt bypasses rewrite
# ---------------------------------------------------------------------------

def test_reformulator_preserves_self_contained_case_prompt() -> None:
    cfg = load_agents_config()
    session = _make_session(
        "What is the RPOD request process?",
        "The answer described the RPOD request workflow.",
    )
    context_mode = ContextModeResult(
        mode="retrieval_followup",
        track="retrieval",
        requires_retrieval=True,
        requires_reformulation=True,
        prior_answer_needed=False,
        mode_confidence="medium",
        mode_method="llm",
        reformulated_query=None,
    )
    query = (
        'Katherine Kim requested RPOD from UNIS for: - DO: 7256988348 '
        '- Load/Pro: 17620449 - Carrier Response: "Hello. Please proceed with claims." '
        "The carrier has confirmed the freight is lost. Per SOP-11: "
        "1. Confirm this triggers immediate claim filing against the carrier "
        "2. Generate the claim filing package "
        "3. Calculate the Carrier Response SLA compliance "
        '4. Update the RA tracking to reflect "Claim Filed" status'
    )

    with _patched_attr(reformulator_module, "_rewrite_followup_query", _raise_model_error):
        result = reformulator_module.run_stage2a(
            query,
            context_mode,
            session,
            cfg.reformulator,
        )

    assert result == query
    assert context_mode.reformulated_query == query


# ---------------------------------------------------------------------------
# Live integration tests — require Ollama on localhost:11434
# ---------------------------------------------------------------------------
# ─────────────────────────────────────────────────────────────────
# GROUP 1 AGENT TEST SCRIPT
# Usage: python tests/test_group1_agents.py
# Requirements: Ollama running on localhost:11434 with gemma3:1B pulled
#               (or whatever model is set in agents.yml)
# ─────────────────────────────────────────────────────────────────
#
# For each test case below, the script:
#   1. Runs the full Group 1 orchestrator
#   2. Prints what each stage decided
#   3. Shows what query would go to retrieval (or that retrieval is skipped)
#   4. That's it. No pass/fail. Just read the output.
#
# If you see sensible decisions in the terminal → your config swap will work.
# If you see garbage → fix the prompt, not the model. Same garbage happens on 70B.

TEST_CASES = [
    {
        "label": "1. Clear in-domain — SOP procedure question",
        "query": "What are the steps to process a freight shortage claim?",
        "session_turns": [],
    },
    {
        "label": "2. Clear in-domain — role lookup from table",
        "query": "Who handles theft incidents and what is their contact email?",
        "session_turns": [],
    },
    {
        "label": "3. In-domain with explicit format request",
        "query": "List the documents required for a return authorization in bullet points",
        "session_turns": [],
    },
    {
        "label": "4. In-domain — comparative style",
        "query": "What is the difference between GR and GI in warehouse operations?",
        "session_turns": [],
    },
    {
        "label": "5. Clear out-of-domain — general knowledge",
        "query": "Who is the president of the United States?",
        "session_turns": [],
    },
    {
        "label": "6. Clear out-of-domain — creative request",
        "query": "Write me a poem about logistics",
        "session_turns": [],
    },
    {
        "label": "7. Borderline — domain word in general question",
        "query": "What is a carrier?",
        "session_turns": [],
    },
    {
        "label": "8. Borderline — partially in-domain",
        "query": "What are industry standard SLA timelines for freight claims?",
        "session_turns": [],
    },
    {
        "label": "9. Answer transform — explicit reformat",
        "query": "Make it shorter",
        "session_turns": [
            {
                "query_original": "What are the steps to process a freight shortage claim?",
                "answer_text": "To process a freight shortage claim: 1. The Credit & Collections Analyst reviews the customer deduction and gathers documentation including invoice number, deduction code, and POD. 2. Send shortage notification to SEACLAIMS and REVERSE_SHORTPAY with invoice number, D/O number, BOL number, shortage quantity and dollar amount. 3. SEACLAIMS validates against POD and shipping records, submits RA for approval, and files carrier claim. 4. Upon RA approval, proceed with claim processing and credit issuance.",
                "route_used": "procedure",
                "style_used": "procedural",
            }
        ],
    },
    {
        "label": "10. Retrieval followup — vague continuation",
        "query": "what about the timeline?",
        "session_turns": [
            {
                "query_original": "What are the steps to process a freight shortage claim?",
                "answer_text": "To process a freight shortage claim, the Credit & Collections Analyst first reviews the deduction and gathers documentation. They then notify SEACLAIMS. The claims team validates and files the carrier claim after RA approval.",
                "route_used": "procedure",
                "style_used": "procedural",
            }
        ],
    },
    {
        "label": "11. Retrieval followup — single word vague",
        "query": "why",
        "session_turns": [
            {
                "query_original": "Who is responsible for managing theft incidents?",
                "answer_text": "Logistics Security is responsible for managing theft incidents, coordinating with law enforcement and carriers. They can be reached at logsec@sea.samsung.com.",
                "route_used": "direct",
                "style_used": "direct",
            }
        ],
    },
    {
        "label": "12. Transform override — domain term present, should become retrieval_followup",
        "query": "summarize the RA process",
        "session_turns": [
            {
                "query_original": "What documents are needed for claims?",
                "answer_text": "You need a signed POD, Debit Memo, invoice details, and BOL/Load ID.",
                "route_used": "direct",
                "style_used": "direct",
            }
        ],
    },
    {
        "label": "13. Standalone despite prior session — complete new question",
        "query": "What is the procedure for handling a returned shipment from Amazon?",
        "session_turns": [
            {
                "query_original": "What is a BOL?",
                "answer_text": "A BOL (Bill of Lading) is a shipping document issued by the carrier.",
                "route_used": "direct",
                "style_used": "direct",
            }
        ],
    },
]


def _build_session(turns_data: list) -> SessionContext:
    """Build a SessionContext from the raw turn dicts in a test case."""
    import datetime

    turns = []
    for t in turns_data:
        turns.append(
            Turn(
                query_original=t.get("query_original", ""),
                query_reformulated=t.get("query_reformulated", None),
                answer_text=t.get("answer_text", ""),
                answer_summary=t.get("answer_summary", None),
                chunk_ids=t.get("chunk_ids", []),
                route_used=t.get("route_used", ""),
                style_used=t.get("style_used", ""),
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                query_vector=None,
            )
        )
    return SessionContext(
        session_id="live-test",
        turns=turns,
        turn_count=len(turns),
    )


_W = 58  # width of the box border
_SEP_DOUBLE = "=" * _W   # section header
_SEP_SINGLE = "-" * _W   # result divider


def _print_stage0(sig) -> None:
    matched = sig.matched_terms if sig.matched_terms else []
    print("STAGE 0 -- Domain Gate (deterministic)")
    print(f"  signal:        {sig.domain_signal}")
    print(f"  gate_decision: {sig.gate_decision}")
    print(f"  matched_terms: {matched}")
    print(f"  match_density: {sig.match_density:.2f}")
    print()


def _print_stage1(u, model_name: str) -> None:
    print(f"STAGE 1 -- Query Understanding (LLM: {model_name})")
    print(f"  in_domain:     {u.in_domain}  [{u.domain_confidence} confidence]")
    print(f"  style:         {u.style}")
    print(f"  format_type:   {u.format_type}")
    print(f"  format_explicit: {u.format_is_explicit}")
    print(f"  length_hint:   {u.length_hint}")
    print(f"  method:        {u.classifier_method}")
    print()


def _print_stage1_skipped(reason: str) -> None:
    print(f"STAGE 1 -- Query Understanding: SKIPPED ({reason})")
    print()


def _print_stage2(cm, session_has_turns: bool) -> None:
    note = "  [no prior session]" if not session_has_turns else ""
    print(f"STAGE 2 -- Context Mode ({cm.mode_method})")
    print(f"  mode:          {cm.mode}")
    print(f"  track:         {cm.track}")
    print(f"  method:        {cm.mode_method}{note}")
    print()


def _print_stage2_skipped(reason: str) -> None:
    print(f"STAGE 2 -- Context Mode: SKIPPED ({reason})")
    print()


def _print_stage2a(cm, was_run: bool) -> None:
    if not was_run:
        print(f"STAGE 2a -- Reformulator: SKIPPED ({cm.mode})")
    else:
        reformulated = cm.reformulated_query or "(passthrough)"
        print(f"STAGE 2a -- Reformulator: RAN")
        print(f"  reformulated:  \"{reformulated}\"")
    print()


def _print_result(r: "Group1Result") -> None:
    print(_SEP_SINGLE)
    print("RESULT:")
    if r.should_refuse:
        print(f"  should_retrieve:   NO -- REFUSED")
        print(f"  reason: \"{r.refusal_message}\"")
    elif not r.should_retrieve:
        print(f"  should_retrieve:   NO -- TRANSFORM ONLY")
        print(f"  note: use last_answer from session, reformat only")
    else:
        print(f"  should_retrieve:   YES")
        print(f"  query_to_retrieve: \"{r.query_for_retrieval}\"")
        print(f"  style injected:    {r.style} / {r.format_type} / {r.length_hint}")
    print(f"  latency:           {r.total_latency_ms:.0f} ms")
    print(_SEP_SINGLE)


def _run_live_test(idx: int, case: dict) -> None:
    label = case["label"]
    query = case["query"]
    turns_data = case["session_turns"]

    print(_SEP_DOUBLE)
    print(f"TEST {label}")
    print(_SEP_DOUBLE)
    print(f"Query: \"{query}\"")
    print(f"Session: {'no prior turns' if not turns_data else f'{len(turns_data)} prior turn(s)'}")
    print()

    session = _build_session(turns_data)

    try:
        cfg = load_agents_config()
        model_name = cfg.query_understanding.model_name
    except Exception:
        model_name = "?"

    result = run_group1(query, session)

    # Determine what ran based on result fields
    stage1_skipped = result.understanding.classifier_method == "skipped"
    stage2_skipped = result.context_mode.mode_method == "skipped"
    stage2a_ran = result.context_mode.mode == "retrieval_followup"

    _print_stage0(result.domain_signal)

    if stage1_skipped:
        _print_stage1_skipped("fast_reject")
    else:
        _print_stage1(result.understanding, model_name)

    if stage2_skipped:
        _print_stage2_skipped("refused before Stage 2")
    else:
        _print_stage2(result.context_mode, bool(turns_data))

    _print_stage2a(result.context_mode, stage2a_ran)

    _print_result(result)
    print()


def _check_ollama() -> bool:
    """Return True if Ollama is reachable on localhost:11434."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434", timeout=3)
        return True
    except Exception:
        return False


def run_live_tests() -> None:
    """Run 13 end-to-end orchestrator test cases against a live Ollama instance."""
    print()
    print("=" * _W)
    print("LIVE INTEGRATION TESTS (requires Ollama)")
    print("=" * _W)

    if not _check_ollama():
        print("[SKIPPED -- Ollama not reachable on localhost:11434]")
        print("Start Ollama and pull the model configured in agents.yml, then re-run.")
        return

    for idx, case in enumerate(TEST_CASES, start=1):
        _run_live_test(idx, case)


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_config_loads,
        test_missing_yaml_raises_file_not_found,
        test_missing_field_raises_key_error,
        test_freight_shortage_claim_clear_in_steps,
        test_out_of_domain_clear_out,
        test_return_authorization_bullets,
        test_creative_request_with_generic_domain_term_is_borderline,
        test_generic_domain_word_is_borderline,
        test_returned_shipment_from_configured_customer_is_clear_in,
        test_session_context_properties_non_empty,
        test_session_context_properties_empty,
        test_query_understanding_procedural_in_domain,
        test_query_understanding_skips_clear_out,
        test_query_understanding_preserves_explicit_bullets,
        test_query_understanding_failure_fallback,
        test_context_mode_answer_transform,
        test_context_mode_retrieval_followup,
        test_context_mode_correction_challenge_followup,
        test_correction_detector_ignores_plain_reformat_preface,
        test_context_mode_standalone_new_question,
        test_context_mode_case_study_prompt_is_standalone_despite_prior_session,
        test_context_mode_transform_override_to_followup,
        test_context_mode_failure_fallback,
        test_context_mode_llm_success,
        test_reformulator_rewrites_followup,
        test_reformulator_preserves_correction_challenge_without_llm,
        test_reformulator_failure_passthrough,
        test_reformulator_invalid_short_output_passthrough,
        test_reformulator_preserves_self_contained_case_prompt,
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

    # --- Live integration tests (require Ollama) ---
    run_live_tests()

    sys.exit(0 if failed == 0 else 1)
