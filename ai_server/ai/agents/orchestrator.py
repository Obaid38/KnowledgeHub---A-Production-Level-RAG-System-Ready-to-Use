"""Agent Orchestrator: coordinates the Stage 0 → 1 → 2 → 2a pipeline.

This is the top-level entry point for the Group 1 agent pipeline.
The FastAPI endpoint calls run_group1() and uses the returned Group1Result
to decide whether to retrieve, refuse, or transform the last answer.
"""
import logging
import time
from dataclasses import dataclass, field

from ai.agents.config.agent_config_loader import load_agents_config
from ai.agents.models.context_mode import ContextModeResult
from ai.agents.models.domain_signal import DomainSignal
from ai.agents.models.query_understanding import QueryUnderstandingResult
from ai.agents.models.retrieval_plan import RetrievalPlanResult
from ai.agents.models.session import SessionContext
from ai.agents.stage0_domain_gate import run_stage0
from ai.agents.stage1_query_understanding import run_stage1
from ai.agents.stage2_context_mode import run_stage2
from ai.agents.stage2a_reformulator import run_stage2a
from ai.agents.stage2b_retrieval_planner import build_fallback_plan, run_stage2b

logger = logging.getLogger(__name__)


@dataclass
class Group1Result:
    """Fully resolved routing decision returned by run_group1().

    Downstream retrieval, refusal, or transform logic consumes this object.
    """

    query_original: str
    query_for_retrieval: str
    domain_signal: DomainSignal
    understanding: QueryUnderstandingResult
    context_mode: ContextModeResult
    should_retrieve: bool
    should_refuse: bool
    refusal_message: str | None
    style: str
    format_type: str
    length_hint: str
    total_latency_ms: float
    retrieval_plan: RetrievalPlanResult | None = None
    stage_latencies: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Private helpers — default objects for short-circuit paths
# ---------------------------------------------------------------------------

def _default_understanding(
    refusal_reason: str | None = None,
    classifier_method: str = "skipped",
) -> QueryUnderstandingResult:
    """Safe fallback QueryUnderstandingResult when Stage 1 is skipped or fails."""
    return QueryUnderstandingResult(
        in_domain=False,
        domain_confidence="low",
        refusal_reason=refusal_reason,
        style="direct",
        format_type="prose",
        format_is_explicit=False,
        length_hint="infer",
        classifier_method=classifier_method,
    )


def _default_context_mode() -> ContextModeResult:
    """Safe fallback ContextModeResult when Stage 2 is skipped or fails."""
    return ContextModeResult(
        mode="standalone",
        track="retrieval",
        requires_retrieval=False,
        requires_reformulation=False,
        prior_answer_needed=False,
        mode_confidence="low",
        mode_method="skipped",
        reformulated_query=None,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_group1(query: str, session: SessionContext) -> Group1Result:
    """Run the full Group 1 pipeline for a query and return a routing decision.

    Always returns a valid Group1Result — never raises.

    Pipeline:
        Stage 0  (deterministic, no LLM) — always runs
        Stage 1  (LLM)                   — skipped on fast_reject
        Stage 2  (regex + LLM fallback)  — skipped on refusal
        Stage 2a (LLM reformulator)      — only for retrieval_followup
    """
    start = time.perf_counter()
    stage_latencies: dict[str, float] = {}

    cfg = load_agents_config()

    # ------------------------------------------------------------------
    # Stage 0 — Domain Gate (deterministic, no LLM)
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    try:
        domain_signal = run_stage0(query, cfg.domain_gate)
        logger.debug(
            "[Orchestrator] Stage 0: signal=%s gate=%s",
            domain_signal.domain_signal,
            domain_signal.gate_decision,
        )
    except Exception as exc:
        logger.error("[Orchestrator] Stage 0 failed unexpectedly: %s", exc)
        domain_signal = DomainSignal(
            domain_signal="unknown",
            format_hint=None,
            format_is_explicit=False,
            matched_terms=[],
            match_density=0.0,
            gate_decision="escalate_to_llm",
        )
    stage_latencies["stage0"] = (time.perf_counter() - _t) * 1000

    # ------------------------------------------------------------------
    # Fast-reject path — skip all LLM stages
    # ------------------------------------------------------------------
    if domain_signal.gate_decision == "fast_reject":
        refusal_msg = "This question does not relate to company documents or operations."
        understanding = _default_understanding(
            refusal_reason=refusal_msg,
            classifier_method="skipped",
        )
        context_mode = _default_context_mode()
        return Group1Result(
            query_original=query,
            query_for_retrieval=query,
            domain_signal=domain_signal,
            understanding=understanding,
            context_mode=context_mode,
            should_retrieve=False,
            should_refuse=True,
            refusal_message=refusal_msg,
            style="direct",
            format_type="prose",
            length_hint="infer",
            total_latency_ms=(time.perf_counter() - start) * 1000,
            retrieval_plan=None,
            stage_latencies=stage_latencies,
        )

    # ------------------------------------------------------------------
    # Stage 1 — Query Understanding (LLM)
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    try:
        understanding = run_stage1(query, domain_signal, cfg.query_understanding)
        logger.debug(
            "[Orchestrator] Stage 1: in_domain=%s confidence=%s style=%s method=%s",
            understanding.in_domain,
            understanding.domain_confidence,
            understanding.style,
            understanding.classifier_method,
        )
    except Exception as exc:
        logger.error("[Orchestrator] Stage 1 failed unexpectedly: %s", exc)
        understanding = _default_understanding(classifier_method="fallback")
    stage_latencies["stage1"] = (time.perf_counter() - _t) * 1000

    # ------------------------------------------------------------------
    # Out-of-domain path — refuse after Stage 1
    # ------------------------------------------------------------------
    if not understanding.in_domain:
        refusal_msg = (
            understanding.refusal_reason
            or "This question does not relate to company documents or operations."
        )
        context_mode = _default_context_mode()
        return Group1Result(
            query_original=query,
            query_for_retrieval=query,
            domain_signal=domain_signal,
            understanding=understanding,
            context_mode=context_mode,
            should_retrieve=False,
            should_refuse=True,
            refusal_message=refusal_msg,
            style=understanding.style,
            format_type=understanding.format_type,
            length_hint=understanding.length_hint,
            total_latency_ms=(time.perf_counter() - start) * 1000,
            retrieval_plan=None,
            stage_latencies=stage_latencies,
        )

    # ------------------------------------------------------------------
    # Stage 2 — Context Mode (regex first, LLM fallback)
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    try:
        context_mode = run_stage2(query, understanding, session, cfg.context_mode)
        logger.debug(
            "[Orchestrator] Stage 2: mode=%s track=%s method=%s",
            context_mode.mode,
            context_mode.track,
            context_mode.mode_method,
        )
    except Exception as exc:
        logger.error("[Orchestrator] Stage 2 failed unexpectedly: %s", exc)
        context_mode = _default_context_mode()
    stage_latencies["stage2"] = (time.perf_counter() - _t) * 1000

    # ------------------------------------------------------------------
    # Stage 2a — Reformulator (only for retrieval_followup)
    # ------------------------------------------------------------------
    _t = time.perf_counter()
    if context_mode.mode == "retrieval_followup":
        try:
            run_stage2a(query, context_mode, session, cfg.reformulator)
            logger.debug(
                "[Orchestrator] Stage 2a: reformulated_query=%s",
                context_mode.reformulated_query,
            )
        except Exception as exc:
            logger.error("[Orchestrator] Stage 2a failed unexpectedly: %s", exc)
            context_mode.reformulated_query = query
    elif context_mode.mode == "citation_lookup":
        logger.info("[Orchestrator] citation_lookup route activated for: %r", query)
    stage_latencies["stage2a"] = (time.perf_counter() - _t) * 1000

    # ------------------------------------------------------------------
    # Stage 2b — Retrieval Planner
    # ------------------------------------------------------------------
    query_for_retrieval = context_mode.reformulated_query or query
    should_retrieve = context_mode.mode not in {"answer_transform", "citation_lookup"}

    retrieval_plan: RetrievalPlanResult | None = None
    _t = time.perf_counter()
    if should_retrieve:
        try:
            retrieval_plan = run_stage2b(
                query_for_retrieval,
                cfg.retrieval_planner,
            )
            logger.debug(
                "[Orchestrator] Stage 2b: planner_method=%s queries=%d",
                retrieval_plan.planner_method,
                len(retrieval_plan.retrieval_queries),
            )
        except Exception as exc:
            logger.error("[Orchestrator] Stage 2b failed unexpectedly: %s", exc)
            retrieval_plan = build_fallback_plan(
                query_for_retrieval,
                method="fallback_orchestrator_error",
            )
    stage_latencies["stage2b"] = (time.perf_counter() - _t) * 1000

    return Group1Result(
        query_original=query,
        query_for_retrieval=query_for_retrieval,
        domain_signal=domain_signal,
        understanding=understanding,
        context_mode=context_mode,
        should_retrieve=should_retrieve,
        should_refuse=False,
        refusal_message=None,
        style=understanding.style,
        format_type=understanding.format_type,
        length_hint=understanding.length_hint,
        total_latency_ms=(time.perf_counter() - start) * 1000,
        retrieval_plan=retrieval_plan,
        stage_latencies=stage_latencies,
    )
