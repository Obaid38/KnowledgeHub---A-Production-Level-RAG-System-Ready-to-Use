"""Step 5b - deterministic faithfulness check.

Regex-scans the generated answer for figures and configured domain entities,
then verifies each extracted item with a case-insensitive substring search over
the retrieved chunk text. This step does not call an LLM, network service, or
vector index.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ai.agents.config.agent_config_loader import load_agents_config
from ai.config.company_profile import load_company_profile

logger = logging.getLogger("knowledge_hub.pipeline.step5b")

_DEFAULT_PENALTY_LOW = 0.10
_DEFAULT_PENALTY_HIGH = 0.20
_CAUTION_MESSAGE = (
    "Some figures or entities in this answer could not be verified against "
    "the source documents. Please verify before use."
)

_RE_MONEY = re.compile(
    r"\$[\d,]+(?:\.\d{2})?|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:USD|dollars?)\b",
    re.IGNORECASE,
)
_RE_PERCENT = re.compile(r"\b\d+(?:\.\d+)?%")
_RE_DATE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b|"
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    re.IGNORECASE,
)
_RE_CLAIM_ID = re.compile(r"\bCLM-\d{4}-\d{4}\b", re.IGNORECASE)
_RE_RA = re.compile(r"\bRA[-#]?\d{4,}\b", re.IGNORECASE)
_RE_BOL = re.compile(r"\bBOL[-#]?\w{4,}\b", re.IGNORECASE)
_PROFILE = load_company_profile()
_CARRIER_NAMES = tuple(_PROFILE.domain.faithfulness_entities)
if _CARRIER_NAMES:
    _RE_CARRIER = re.compile(
        r"(?<!\w)("
        + "|".join(re.escape(name).replace(r"\ ", r"\s+") for name in _CARRIER_NAMES)
        + r")(?!\w)",
        re.IGNORECASE,
    )
else:
    _RE_CARRIER = re.compile(r"(?!x)x")


@dataclass
class FaithfulnessResult:
    passed: bool
    suspicious_entities: list[str] = field(default_factory=list)
    suspicious_figures: list[str] = field(default_factory=list)
    confidence_penalty: float = 0.0
    check_skipped: bool = False
    caution_message: str | None = None


def _read_value(chunk: object, names: tuple[str, ...], default: Any = None) -> Any:
    if isinstance(chunk, dict):
        for name in names:
            if name in chunk and chunk[name] is not None:
                return chunk[name]
        return default

    for name in names:
        value = getattr(chunk, name, None)
        if value is not None:
            return value
    return default


def _extract_chunk_text(chunk: object) -> str:
    value = _read_value(chunk, ("chunk_text", "text", "content", "page_content"), "")
    return value if isinstance(value, str) else str(value or "")


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
    return result


def _load_faithfulness_config() -> tuple[bool, float, float]:
    try:
        cfg = load_agents_config().faithfulness_check
        return cfg.enabled, cfg.penalty_low, cfg.penalty_high
    except Exception as exc:
        logger.warning("[Step5b] Config load failed, using defaults: %s", exc)
        return True, _DEFAULT_PENALTY_LOW, _DEFAULT_PENALTY_HIGH


def _verified(item: str, source_text: str) -> bool:
    return item.casefold() in source_text


def _penalty_for_count(count: int, penalty_low: float, penalty_high: float) -> float:
    if count == 0:
        return 0.0
    if count <= 2:
        return penalty_low
    return penalty_high


def run_faithfulness_check(
    answer_text: str,
    chunks: list,
    allowed_context: list[str] | None = None,
) -> FaithfulnessResult:
    """Check extracted answer figures/entities against retrieved text and user facts."""
    enabled, penalty_low, penalty_high = _load_faithfulness_config()

    if not enabled or not chunks:
        return FaithfulnessResult(passed=True, check_skipped=True)

    context_text = "\n".join(
        item for item in (allowed_context or [])
        if isinstance(item, str) and item.strip()
    )
    source_text = (
        "\n".join(_extract_chunk_text(chunk) for chunk in chunks)
        + "\n"
        + context_text
    ).casefold()

    figures = _dedupe_preserve_order(
        _RE_MONEY.findall(answer_text)
        + _RE_PERCENT.findall(answer_text)
        + _RE_DATE.findall(answer_text)
    )
    carrier_entities = [
        match.group(0)
        for match in _RE_CARRIER.finditer(answer_text)
    ]
    entities = _dedupe_preserve_order(
        carrier_entities
        + _RE_CLAIM_ID.findall(answer_text)
        + _RE_RA.findall(answer_text)
        + _RE_BOL.findall(answer_text)
    )

    suspicious_figures = [
        item for item in figures
        if not _verified(item, source_text)
    ]
    suspicious_entities = [
        item for item in entities
        if not _verified(item, source_text)
    ]

    suspicious_count = len(suspicious_figures) + len(suspicious_entities)
    passed = suspicious_count == 0

    return FaithfulnessResult(
        passed=passed,
        suspicious_entities=suspicious_entities,
        suspicious_figures=suspicious_figures,
        confidence_penalty=_penalty_for_count(suspicious_count, penalty_low, penalty_high),
        check_skipped=False,
        caution_message=None if passed else _CAUTION_MESSAGE,
    )
