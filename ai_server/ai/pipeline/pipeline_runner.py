"""Pipeline Runner - single entry point chaining all pipeline steps.

Each step is added here as it is implemented. Downstream callers
(FastAPI endpoints, tests) import run_pipeline and PipelineState only -
they never import individual step modules directly.

Current steps:
  Step 1 - Retrieval Gate  (Group 1 routing + Qdrant search)
  Step 2 - Confidence Gate (threshold check on top_score)
  Step 3 - Prompt Assembler (deterministic string assembly)
  Step 4 - Answer Generator (Ollama LLM call)
  Step 5a - Citation Builder (metadata-only)
  Step 5b - Faithfulness Check (regex + substring verification)
  Step 6 - Turn construction + session.add_turn() (session persistence)
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai.agents.models.session import SessionContext, Turn
from ai.pipeline.step1_retrieval_gate import RetrievalResult, run_retrieval_gate
from ai.retrieval.query_embedder import embed_query
from ai.pipeline.step2_confidence_gate import ConfidenceGateResult, run_confidence_gate
from ai.pipeline.step3_prompt_assembler import PromptAssemblerResult, run_prompt_assembler
from ai.pipeline.step4_answer_generator import AnswerGeneratorResult, run_answer_generator
from ai.pipeline.step5a_citation_builder import CitationResult, run_citation_builder
from ai.pipeline.step5b_faithfulness_check import FaithfulnessResult, run_faithfulness_check

logger = logging.getLogger("knowledge_hub.pipeline")


def _build_citation_answer(query: str, session: SessionContext) -> str:
    """Build a deterministic natural-language answer from session.last_citations.

    No LLM, no Qdrant, no embeddings. Under 1ms.
    """
    citations = session.last_citations
    if not citations:
        return (
            "I don't have citation information available for the previous "
            "answer. Please ask a new question."
        )

    query_lower = query.lower()

    # Page number question
    if any(p in query_lower for p in ["page", "pg."]):
        parts = []
        for c in citations:
            fn = c.get("source_filename", "unknown document")
            pg = c.get("page_number")
            sh = c.get("section_heading")
            if pg:
                loc = f"page {pg}"
                if sh:
                    loc += f", section §{sh}"
                parts.append(f"{fn} ({loc})")
            else:
                parts.append(f"{fn} (page number not available for this format)")
        if len(parts) == 1:
            return f"That information was found in {parts[0]}."
        return "That information was sourced from:\n" + "\n".join(
            f"  [{c['rank']}] {p}" for c, p in zip(citations, parts)
        )

    # Section / heading question
    if any(p in query_lower for p in ["section", "heading", "chapter"]):
        parts = []
        for c in citations:
            fn = c.get("source_filename", "unknown document")
            sh = c.get("section_heading")
            if sh:
                parts.append(f"§{sh} of {fn}")
            else:
                parts.append(f"{fn} (no section heading detected)")
        if len(parts) == 1:
            return f"That was covered in {parts[0]}."
        return "That information appeared across:\n" + "\n".join(
            f"  [{c['rank']}] {p}" for c, p in zip(citations, parts)
        )

    # Document / source / file question (default for all other citation queries)
    if len(citations) == 1:
        c = citations[0]
        fn = c.get("source_filename", "unknown document")
        pg = c.get("page_number")
        sh = c.get("section_heading")
        response = f"That information came from **{fn}**"
        if pg:
            response += f", page {pg}"
        if sh:
            response += f", section §{sh}"
        response += "."
        return response

    # Multiple sources
    lines = []
    for c in citations:
        fn = c.get("source_filename", "unknown")
        pg = c.get("page_number")
        sh = c.get("section_heading")
        line = f"[SOURCE {c['rank']}] {fn}"
        if pg:
            line += f", p.{pg}"
        if sh:
            line += f", §{sh}"
        lines.append(line)
    return (
        f"The previous answer drew from {len(citations)} source(s):\n"
        + "\n".join(lines)
    )


def _build_transform_prompt_result(
    prior_answer: str,
    user_request: str,
    confidence_result: ConfidenceGateResult,
) -> PromptAssemblerResult:
    """Build a PromptAssemblerResult for an answer-transform request.

    No Qdrant, no chunks. The prior answer is embedded verbatim into the
    prompt so the LLM can reformat it without hallucinating new content.
    """
    def _transform_format_type(request: str) -> str:
        lowered = request.lower()
        if ("bullet" in lowered or "list" in lowered) and "numbered" not in lowered:
            return "bullets"
        return "prose"

    _MAX_PRIOR_CHARS = 3000
    if len(prior_answer) > _MAX_PRIOR_CHARS:
        prior_answer = prior_answer[:_MAX_PRIOR_CHARS] + "\n[... truncated ...]"

    system_prompt = (
        "You are a text-reformatting assistant. Reformat the answer below exactly "
        "as the user requests. Do not add new information. Do not remove factual "
        "content unless the user explicitly asks for a shorter version. "
        "Output only the reformatted answer — no preamble, no explanation."
    )
    assembled_prompt = (
        f'Previous answer:\n"""\n{prior_answer}\n"""\n\n'
        f"User request: {user_request}\n\n"
        f"Reformatted answer:"
    )
    return PromptAssemblerResult(
        assembled_prompt=assembled_prompt,
        system_prompt=system_prompt,
        chunk_count_used=0,
        format_instruction="",
        format_type=_transform_format_type(user_request),
        style_used="direct",
        was_skipped=False,      # ← must be False so Step 4 calls Ollama
        skip_reason=None,
        confidence_result=confidence_result,
    )


def _planner_allowed_context(retrieval_result: RetrievalResult | None) -> list[str]:
    if retrieval_result is None:
        return []
    plan = retrieval_result.group1_result.retrieval_plan
    if plan is None:
        return []
    return [
        item for item in (plan.case_facts + plan.preserve_for_answer)
        if isinstance(item, str) and item.strip()
    ]


_TRACE_WIDTH = 92  # content width of the header/footer separator lines


def _fmt_ms(ms: float | None) -> str:
    """Format a millisecond duration for trace display."""
    if ms is None:
        return "—"
    if ms < 1:
        return "<1ms"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.2f}s"


def _trace_row(label: str, name: str, detail: str, lat_ms: float | None) -> str:
    """Build one fixed-width trace row.

    Columns: label(5) · name(22) · detail(48) · latency(8, right-aligned).
    """
    return f"│  {label:<5}  {name:<22}  {detail:<48}  {_fmt_ms(lat_ms):>8}"


@dataclass
class PipelineState:
    query: str
    session: SessionContext
    retrieval_result: RetrievalResult | None = field(default=None)
    confidence_result: ConfidenceGateResult | None = field(default=None)
    prompt_result: PromptAssemblerResult | None = field(default=None)
    answer_result: AnswerGeneratorResult | None = field(default=None)
    citation_result: CitationResult | None = field(default=None)
    faithfulness_result: FaithfulnessResult | None = field(default=None)


def run_pipeline(
    query: str,
    session: SessionContext,
    collection: str | list[str] | None = None,
) -> PipelineState:
    """Run all pipeline steps in order and return the accumulated state.

    Always returns a valid PipelineState - individual steps never raise.
    """
    pipeline_start = time.perf_counter()
    state = PipelineState(query=query, session=session)

    # Step 1 - Route query and retrieve chunks
    state.retrieval_result = run_retrieval_gate(query, session, requested_collection=collection)

    # ── citation_lookup bypass ─────────────────────────────────────────────────
    # Activated when Stage 2 detected a citation-intent query AND
    # session.last_citations is populated (guard enforced in Stage 2).
    # Answers deterministically from session metadata — no Qdrant, no LLM.
    _g1 = state.retrieval_result.group1_result if state.retrieval_result else None
    if _g1 and _g1.context_mode.mode == "citation_lookup":
        _bypass_answer = _build_citation_answer(state.query, state.session)
        # Step 2 is instant for non-retrieval paths (returns "skipped_no_retrieval")
        state.confidence_result = run_confidence_gate(state.retrieval_result)
        # Synthetic Step 3 and 4 results satisfy the response builder without LLM
        state.prompt_result = PromptAssemblerResult(
            assembled_prompt="", system_prompt="", chunk_count_used=0,
            format_instruction="", format_type="bullets",
            style_used="direct", was_skipped=True,
            skip_reason="citation_lookup", confidence_result=state.confidence_result,
        )
        state.answer_result = AnswerGeneratorResult(
            answer_text=_bypass_answer, was_generated=True, skip_reason=None,
            model_used="deterministic", latency_ms=0.0,
            prompt_token_estimate=0, no_think_injected=False,
            prompt_result=state.prompt_result,
        )
        # Step 5a/5b run with empty chunks — citation_method="none", check_skipped=True
        state.citation_result = run_citation_builder(answer_text=_bypass_answer, chunks=[])
        state.faithfulness_result = run_faithfulness_check(answer_text=_bypass_answer, chunks=[])
        # Do NOT add a Turn — would overwrite session.last_citations with None
        _log_pipeline_trace(state, pipeline_start)
        return state

    # ── answer_transform bypass ───────────────────────────────────────────────
    # Activated when Stage 2 detected a format-transform request ("make it
    # shorter", "put in bullets", etc.). Reads session.last_answer and calls
    # the LLM to reformat it — no Qdrant, no retrieval. A new Turn IS added
    # (unlike citation_lookup) so the reformatted text becomes the new
    # last_answer for subsequent turns, while last_citations is preserved.
    if _g1 and _g1.context_mode.mode == "answer_transform":
        prior_answer = state.session.last_answer
        state.confidence_result = run_confidence_gate(state.retrieval_result)

        if not prior_answer:
            # No prior answer in session — return a helpful message, no LLM call
            _no_ans = (
                "There is no previous answer to reformat. Please ask a question first."
            )
            state.prompt_result = PromptAssemblerResult(
                assembled_prompt="", system_prompt="", chunk_count_used=0,
                format_instruction="", format_type="",
                style_used="", was_skipped=True,
                skip_reason="no_prior_answer",
                confidence_result=state.confidence_result,
            )
            state.answer_result = AnswerGeneratorResult(
                answer_text=_no_ans, was_generated=False,
                skip_reason="no_prior_answer", model_used="deterministic",
                latency_ms=0.0, prompt_token_estimate=0, no_think_injected=False,
                prompt_result=state.prompt_result,
            )
        else:
            state.prompt_result = _build_transform_prompt_result(
                prior_answer, state.query, state.confidence_result
            )
            state.answer_result = run_answer_generator(state.prompt_result)

            if state.answer_result.was_generated:
                # Preserve session.last_citations from prior turn so
                # citation_lookup still works immediately after a transform.
                _turn = Turn(
                    query_original=state.query,
                    query_reformulated=None,
                    answer_text=state.answer_result.answer_text,
                    answer_summary=None,
                    chunk_ids=[],
                    route_used="answer_transform",
                    style_used="direct",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    query_vector=[],
                    citations=state.session.last_citations,
                    chunks=[],
                    top_score=None,
                )
                state.session.add_turn(_turn)

        state.citation_result = run_citation_builder(
            answer_text=state.answer_result.answer_text, chunks=[]
        )
        state.faithfulness_result = run_faithfulness_check(
            answer_text=state.answer_result.answer_text, chunks=[]
        )
        _log_pipeline_trace(state, pipeline_start)
        return state

    # Step 2 - Evaluate chunk quality against configured threshold
    state.confidence_result = run_confidence_gate(state.retrieval_result)

    # Step 3 - Deterministically assemble the final LLM prompt
    state.prompt_result = run_prompt_assembler(state.confidence_result)

    # Step 4 - Generate answer via Ollama LLM
    state.answer_result = run_answer_generator(state.prompt_result)

    # Step 5 - Run deterministic post-generation quality checks
    answer_text = state.answer_result.answer_text if state.answer_result else ""
    chunks = (
        state.retrieval_result.chunks
        if state.answer_result and state.answer_result.was_generated and state.retrieval_result
        else []
    )
    state.citation_result = run_citation_builder(answer_text=answer_text, chunks=chunks)
    state.faithfulness_result = run_faithfulness_check(
        answer_text=answer_text,
        chunks=chunks,
        allowed_context=_planner_allowed_context(state.retrieval_result),
    )

    # ── Step 6: Turn construction and session update ───────────────────────────
    # Only runs when an answer was actually generated (not refused / confidence-failed).
    if state.answer_result and state.answer_result.was_generated:
        _g1 = state.retrieval_result.group1_result if state.retrieval_result else None

        # Prefer reformulated query for embedding — semantically richer for future context selection
        _query_to_embed = (
            (_g1.context_mode.reformulated_query if _g1 else None)
            or (_g1.query_for_retrieval if _g1 else None)
            or state.query
        )

        # Pre-embed with nomic-embed-text — failure must NOT fail the pipeline
        try:
            _query_vector = embed_query(_query_to_embed)
            # embed_query returns list[float] but normalize defensively
            if hasattr(_query_vector, "tolist"):
                _query_vector = _query_vector.tolist()
            else:
                _query_vector = list(_query_vector)
        except Exception as _emb_err:
            logger.warning("Turn pre-embedding failed: %s. Storing empty vector.", _emb_err)
            _query_vector = []

        # Build citations list from Step 5a output as plain dicts
        _turn_citations = None
        if state.citation_result and state.citation_result.citations:
            _turn_citations = [
                {
                    "rank":              c.rank,
                    "source_filename":   c.source_filename,
                    "page_number":       c.page_number,
                    "section_heading":   c.section_heading,
                    "score_pct":         c.score_pct,
                    "category":          c.category,
                    "extraction_method": c.extraction_method,
                    "upload_date":       c.upload_date,
                    "chunk_indices":     c.chunk_indices,
                }
                for c in state.citation_result.citations
            ]

        _turn = Turn(
            query_original=state.query,
            query_reformulated=_g1.context_mode.reformulated_query if _g1 else None,
            answer_text=state.answer_result.answer_text,
            answer_summary=None,
            chunk_ids=[],
            route_used=_g1.context_mode.mode if _g1 else "unknown",
            style_used=_g1.style if _g1 else "direct",
            timestamp=datetime.now(timezone.utc).isoformat(),
            query_vector=_query_vector,
            citations=_turn_citations,
            chunks=state.retrieval_result.chunks if state.retrieval_result else [],
            top_score=state.retrieval_result.top_score if state.retrieval_result else None,
        )
        state.session.add_turn(_turn)

    _log_pipeline_trace(state, pipeline_start)

    return state


def _log_pipeline_trace(state: PipelineState, pipeline_start: float) -> None:
    """Log a clean fixed-width pipeline trace with per-stage latency and total."""
    total_ms = (time.perf_counter() - pipeline_start) * 1000

    rr = state.retrieval_result
    cr = state.confidence_result
    pr = state.prompt_result
    ar = state.answer_result
    cit = state.citation_result
    faith = state.faithfulness_result

    g1 = rr.group1_result if rr else None
    ds = g1.domain_signal if g1 else None
    qu = g1.understanding if g1 else None
    cm = g1.context_mode if g1 else None
    rp = g1.retrieval_plan if g1 else None
    lats: dict[str, float] = (g1.stage_latencies if g1 else {}) or {}

    logger.info("┌─ Pipeline Trace %s", "─" * (_TRACE_WIDTH - 17))

    # Stage 0 — domain gate
    if ds:
        detail = (
            f"{ds.domain_signal} → {ds.gate_decision}"
            f"  density={ds.match_density:.2f}  matched={len(ds.matched_terms or [])}"
        )
        logger.info(_trace_row("S0", "domain_gate", detail, lats.get("stage0")))

    # Stage 1 — query understanding
    if qu:
        status = "in_domain" if qu.in_domain else "out_of_domain"
        detail = f"{status}  conf={qu.domain_confidence}  style={qu.style}  fmt={qu.format_type}"
        logger.info(_trace_row("S1", "query_understanding", detail, lats.get("stage1")))

    # Stage 2 — context mode
    if cm:
        detail = f"mode={cm.mode}  track={cm.track}  method={cm.mode_method}"
        logger.info(_trace_row("S2", "context_mode", detail, lats.get("stage2")))

    # Stage 2a — reformulator
    if cm:
        if cm.mode == "retrieval_followup" and cm.reformulated_query:
            q = cm.reformulated_query
            preview = (q[:38] + "…") if len(q) > 38 else q
            logger.info(_trace_row("S2a", "reformulator", f"→ {preview!r}", lats.get("stage2a")))
        else:
            logger.info(_trace_row("S2a", "reformulator", f"skipped ({cm.mode})", None))

    # Stage 2b — retrieval planner
    if rp:
        detail = (
            f"case_context={rp.case_context_present}"
            f"  tasks={len(rp.tasks)}  queries={len(rp.retrieval_queries)}"
        )
        logger.info(_trace_row("S2b", "retrieval_planner", detail, lats.get("stage2b")))
    elif cm:
        logger.info(_trace_row("S2b", "retrieval_planner", f"skipped ({cm.mode})", None))

    # Step 1 — retrieval
    if rr:
        if rr.was_refused:
            logger.info(_trace_row("Step1", "retrieval", f"refused  {rr.refusal_message or ''}", None))
        elif not rr.was_retrieved:
            logger.info(_trace_row("Step1", "retrieval", "skipped (no retrieval needed)", None))
        else:
            # Subtract Group1 orchestrator time to show pure embed+search cost
            retrieval_only_ms = max(0.0, rr.latency_ms - (g1.total_latency_ms if g1 else 0.0))
            detail = (
                f"subq={len(rp.retrieval_queries) if rp else 1}"
                f"  chunks={rr.chunk_count}  top={rr.top_score:.4f}"
                f"  planner={rr.planner_used}"
            )
            logger.info(_trace_row("Step1", "retrieval", detail, retrieval_only_ms))

    # Step 2 — confidence gate
    if cr:
        detail = f"{cr.reason}  top={cr.top_score:.4f}  thresh={cr.threshold_used:.3f}"
        logger.info(_trace_row("Step2", "confidence_gate", detail, None))

    # Step 3 — prompt assembler
    if pr:
        if pr.was_skipped:
            logger.info(_trace_row("Step3", "prompt_assembler", f"skipped ({pr.skip_reason})", None))
        else:
            detail = f"style={pr.style_used}  fmt={pr.format_type}  chunks_used={pr.chunk_count_used}"
            logger.info(_trace_row("Step3", "prompt_assembler", detail, None))

    # Step 4 — answer generator
    if ar:
        ans_len = len(ar.answer_text) if ar.answer_text else 0
        detail = f"model={ar.model_used}  tokens~{ar.prompt_token_estimate}  len={ans_len}"
        logger.info(_trace_row("Step4", "answer_generator", detail, ar.latency_ms if ar.was_generated else None))

    # Step 5 — citations + faithfulness
    if cit and faith:
        detail = (
            f"sources={len(cit.citations)}  method={cit.citation_method}"
            f"  faithful={faith.passed}  penalty={faith.confidence_penalty:.2f}"
        )
        logger.info(_trace_row("Step5", "citations+faith", detail, None))

    logger.info("├%s", "─" * (_TRACE_WIDTH - 1))
    logger.info("│  %-77s  %s", "Total", f"{_fmt_ms(total_ms):>8}")
    logger.info("└%s", "─" * (_TRACE_WIDTH - 1))
