"""Loader for agents.yml.

Parses YAML into typed AgentsConfig dataclasses and caches the result as a
module-level singleton. Raises explicit errors on missing file or missing fields —
never silently uses None for required config values.

Usage:
    from ai.agents.config.agent_config_loader import load_agents_config

    cfg = load_agents_config()
    print(cfg.query_understanding.model_name)
"""
import logging
import os
from pathlib import Path

import yaml

from ai.agents.config.agent_config_schema import (
    AgentsConfig,
    AnswerGeneratorConfig,
    CitationBuilderConfig,
    ConfidenceGateConfig,
    DomainGateConfig,
    FaithfulnessCheckConfig,
    LLMConfig,
    PromptAssemblyConfig,
    SessionStoreConfig,
)

logger = logging.getLogger(__name__)

_AGENTS_YML: Path = Path(__file__).parent / "agents.yml"
_config_cache: AgentsConfig | None = None


def _require(section: dict, key: str):
    """Return section[key] or raise KeyError(key) if absent."""
    if key not in section:
        raise KeyError(key)
    return section[key]


def _parse_domain_gate(raw: dict) -> DomainGateConfig:
    return DomainGateConfig(
        strong_in_domain_threshold=float(_require(raw, "strong_in_domain_threshold")),
        strong_out_domain_threshold=float(_require(raw, "strong_out_domain_threshold")),
        min_token_length=int(_require(raw, "min_token_length")),
    )


def _parse_confidence_gate(raw: dict) -> ConfidenceGateConfig:
    return ConfidenceGateConfig(
        default_threshold=float(_require(raw, "default_threshold")),
        thresholds_by_style={
            str(k): float(v)
            for k, v in raw.get("thresholds_by_style", {}).items()
        },
    )


def _parse_prompt_assembly(raw: dict) -> PromptAssemblyConfig:
    return PromptAssemblyConfig(
        vocabulary_block_enabled=bool(_require(raw, "vocabulary_block_enabled")),
        max_chunks_in_prompt=int(_require(raw, "max_chunks_in_prompt")),
        source_header_template=str(_require(raw, "source_header_template")),
        default_style=str(_require(raw, "default_style")),
        max_chunks_by_style={
            str(k): int(v)
            for k, v in raw.get("max_chunks_by_style", {}).items()
        },
    )


def _parse_answer_generator(raw: dict) -> AnswerGeneratorConfig:
    # OLLAMA_URL env var (set in .env.runpod) takes priority over the
    # hardcoded value in agents.yml so Docker deployments don't need to edit
    # the YAML file to point at the ollama container hostname.
    ollama_base_url = os.getenv("OLLAMA_URL") or str(_require(raw, "ollama_base_url"))
    return AnswerGeneratorConfig(
        model_name=str(_require(raw, "model_name")),
        ollama_base_url=ollama_base_url,
        timeout_seconds=int(_require(raw, "timeout_seconds")),
        temperature=float(_require(raw, "temperature")),
        max_tokens=int(_require(raw, "max_tokens")),
        no_think_enabled=bool(raw.get("no_think_enabled", True)),
        no_think_model_prefixes=[
            str(p) for p in raw.get("no_think_model_prefixes", ["qwen3", "qwen3.5"])
        ],
    )


def _parse_citation_builder(raw: dict) -> CitationBuilderConfig:
    return CitationBuilderConfig(
        staleness_threshold_days=int(_require(raw, "staleness_threshold_days")),
        max_citations_in_response=int(_require(raw, "max_citations_in_response")),
    )


def _parse_session_store(raw: dict) -> SessionStoreConfig:
    return SessionStoreConfig(
        ttl_seconds=int(raw.get("ttl_seconds", 3600)),
        max_turns_in_window=int(raw.get("max_turns_in_window", 4)),
        key_prefix=str(raw.get("key_prefix", "session:v1:")),
        enabled=bool(raw.get("enabled", True)),
    )


def _parse_faithfulness_check(raw: dict) -> FaithfulnessCheckConfig:
    return FaithfulnessCheckConfig(
        penalty_low=float(_require(raw, "penalty_low")),
        penalty_high=float(_require(raw, "penalty_high")),
        enabled=bool(_require(raw, "enabled")),
    )


def _parse_llm(raw: dict) -> LLMConfig:
    return LLMConfig(
        provider=str(_require(raw, "provider")),
        model_name=str(_require(raw, "model_name")),
        temperature=float(_require(raw, "temperature")),
        max_tokens=int(_require(raw, "max_tokens")),
        timeout_seconds=int(_require(raw, "timeout_seconds")),
        fallback_behavior=str(_require(raw, "fallback_behavior")),
    )


def load_agents_config() -> AgentsConfig:
    """Load and cache AgentsConfig from agents.yml.

    Raises:
        FileNotFoundError: if agents.yml does not exist at the expected path.
        KeyError: with the missing key name if any required field is absent.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not _AGENTS_YML.exists():
        raise FileNotFoundError(
            f"[AGENTS CONFIG] agents.yml not found at expected path: {_AGENTS_YML}"
        )

    with _AGENTS_YML.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    # Top-level section presence
    for top_key in ("domain_gate", "query_understanding", "context_mode", "reformulator"):
        if top_key not in raw:
            raise KeyError(top_key)

    query_understanding = _parse_llm(raw["query_understanding"])
    context_mode = _parse_llm(raw["context_mode"])
    reformulator = _parse_llm(raw["reformulator"])
    retrieval_planner_raw = raw.get("retrieval_planner")
    retrieval_planner = (
        _parse_llm(retrieval_planner_raw)
        if retrieval_planner_raw is not None
        else LLMConfig(
            provider=query_understanding.provider,
            model_name=query_understanding.model_name,
            temperature=0.0,
            max_tokens=900,
            timeout_seconds=query_understanding.timeout_seconds,
            fallback_behavior="passthrough_single_query",
        )
    )

    # confidence_gate is optional for backward compat — defaults to 0.4 if absent
    _confidence_gate_raw = raw.get("confidence_gate")
    confidence_gate = (
        _parse_confidence_gate(_confidence_gate_raw)
        if _confidence_gate_raw is not None
        else ConfidenceGateConfig(default_threshold=0.4, thresholds_by_style={})
    )

    prompt_assembly_raw = raw.get("prompt_assembly")
    prompt_assembly = (
        _parse_prompt_assembly(prompt_assembly_raw)
        if prompt_assembly_raw is not None
        else PromptAssemblyConfig(
            vocabulary_block_enabled=True,
            max_chunks_in_prompt=5,
            source_header_template="[SOURCE {n}]",
            default_style="exploratory",
        )
    )

    answer_generator_raw = raw.get("answer_generator")
    answer_generator = (
        _parse_answer_generator(answer_generator_raw)
        if answer_generator_raw is not None
        else AnswerGeneratorConfig(
            model_name="gemma3:1b",
            ollama_base_url="http://localhost:11434",
            timeout_seconds=120,
            temperature=0.1,
            max_tokens=1024,
            no_think_enabled=True,
            no_think_model_prefixes=["qwen3", "qwen3.5"],
        )
    )

    citation_builder_raw = raw.get("citation_builder")
    citation_builder = (
        _parse_citation_builder(citation_builder_raw)
        if citation_builder_raw is not None
        else CitationBuilderConfig(
            staleness_threshold_days=180,
            max_citations_in_response=5,
        )
    )

    faithfulness_check_raw = raw.get("faithfulness_check")
    faithfulness_check = (
        _parse_faithfulness_check(faithfulness_check_raw)
        if faithfulness_check_raw is not None
        else FaithfulnessCheckConfig(
            penalty_low=0.10,
            penalty_high=0.20,
            enabled=True,
        )
    )

    session_store_raw = raw.get("session_store")
    session_store = (
        _parse_session_store(session_store_raw)
        if session_store_raw is not None
        else SessionStoreConfig(
            ttl_seconds=3600,
            max_turns_in_window=4,
            key_prefix="session:v1:",
            enabled=True,
        )
    )

    _config_cache = AgentsConfig(
        domain_gate=_parse_domain_gate(raw["domain_gate"]),
        query_understanding=query_understanding,
        context_mode=context_mode,
        reformulator=reformulator,
        retrieval_planner=retrieval_planner,
        confidence_gate=confidence_gate,
        prompt_assembly=prompt_assembly,
        answer_generator=answer_generator,
        citation_builder=citation_builder,
        faithfulness_check=faithfulness_check,
        session_store=session_store,
    )

    logger.info(
        "[AGENTS CONFIG] Loaded. query_understanding.model=%s answer_generator.model=%s",
        _config_cache.query_understanding.model_name,
        _config_cache.answer_generator.model_name,
    )

    return _config_cache
