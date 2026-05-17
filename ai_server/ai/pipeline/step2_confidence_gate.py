"""Step 2 — Confidence Gate.

Evaluates whether the top retrieved chunk score clears the configured
threshold for the query's style. All thresholds live in agents.yml under
the confidence_gate key — no values are hardcoded here.

Gate decisions:
  passed              — top_score >= threshold, proceed to answer generation
  below_threshold     — retrieval ran but top score was too low
  no_chunks           — retrieval ran but returned nothing
  skipped_no_retrieval — refused or answer_transform path, gate does not apply
  gate_error          — unexpected failure, treated as not-passed
"""
import logging
from dataclasses import dataclass

from ai.agents.config.agent_config_loader import load_agents_config
from ai.pipeline.step1_retrieval_gate import RetrievalResult

logger = logging.getLogger("knowledge_hub.pipeline.step2")


@dataclass
class ConfidenceGateResult:
    passed: bool                       # True = chunks cleared the bar, proceed
    top_score: float                   # the score that was evaluated
    threshold_used: float              # the threshold compared against
    style_used: str                    # style key that drove threshold lookup
    chunk_count: int                   # how many chunks came in from Step 1
    reason: str                        # "passed" / "below_threshold" / "no_chunks" /
                                       # "skipped_no_retrieval" / "gate_error"
    retrieval_result: RetrievalResult  # pass-through from Step 1


def run_confidence_gate(retrieval_result: RetrievalResult) -> ConfidenceGateResult:
    """Evaluate whether Step 1 results are good enough to proceed.

    Thresholds are loaded from agents.yml confidence_gate section.
    No thresholds are hardcoded — edit agents.yml and restart to reconfigure.

    Always returns a valid ConfidenceGateResult — never raises.
    """
    # 1. Skip gate entirely for refused or non-retrieval paths
    if retrieval_result.was_refused or not retrieval_result.was_retrieved:
        return ConfidenceGateResult(
            passed=False,
            top_score=0.0,
            threshold_used=0.0,
            style_used="",
            chunk_count=0,
            reason="skipped_no_retrieval",
            retrieval_result=retrieval_result,
        )

    try:
        # 2. Load threshold from config — driven by the query's style
        cfg = load_agents_config()
        style = retrieval_result.group1_result.style
        threshold = cfg.confidence_gate.threshold_for_style(style)

        logger.debug(
            "[Step2] style=%r threshold=%.3f top_score=%.4f chunk_count=%d",
            style,
            threshold,
            retrieval_result.top_score,
            retrieval_result.chunk_count,
        )

        # 3. No chunks or zero score — retrieval ran but found nothing usable
        if retrieval_result.chunk_count == 0 or retrieval_result.top_score == 0.0:
            logger.info(
                "[Step2] no_chunks: style=%r threshold=%.3f",
                style,
                threshold,
            )
            return ConfidenceGateResult(
                passed=False,
                top_score=retrieval_result.top_score,
                threshold_used=threshold,
                style_used=style,
                chunk_count=retrieval_result.chunk_count,
                reason="no_chunks",
                retrieval_result=retrieval_result,
            )

        # 4. Compare score against threshold
        passed = retrieval_result.top_score >= threshold
        reason = "passed" if passed else "below_threshold"

        logger.info(
            "[Step2] %s: style=%r top_score=%.4f threshold=%.3f",
            reason,
            style,
            retrieval_result.top_score,
            threshold,
        )

        return ConfidenceGateResult(
            passed=passed,
            top_score=retrieval_result.top_score,
            threshold_used=threshold,
            style_used=style,
            chunk_count=retrieval_result.chunk_count,
            reason=reason,
            retrieval_result=retrieval_result,
        )

    except Exception as exc:
        logger.error("[Step2] Confidence gate failed: %s", exc)
        return ConfidenceGateResult(
            passed=False,
            top_score=retrieval_result.top_score,
            threshold_used=0.0,
            style_used="",
            chunk_count=retrieval_result.chunk_count,
            reason="gate_error",
            retrieval_result=retrieval_result,
        )
