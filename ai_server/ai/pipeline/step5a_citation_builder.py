"""Step 5a - deterministic citation builder.

Builds answer citations from retrieved chunk metadata only. This step does not
call an LLM, network service, or vector index.
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ai.agents.config.agent_config_loader import load_agents_config

logger = logging.getLogger("knowledge_hub.pipeline.step5a")

_DEFAULT_STALENESS_THRESHOLD_DAYS = 180
_DEFAULT_MAX_CITATIONS = 5


@dataclass
class Citation:
    rank: int
    source_filename: str
    page_number: int | None
    section_heading: str | None
    score: float
    score_pct: int
    category: str
    upload_date: str | None
    extraction_method: str
    chunk_indices: list[int] = field(default_factory=list)


@dataclass
class CitationResult:
    citations: list[Citation]
    citation_method: str
    any_stale_source: bool
    ocr_sources_present: bool
    cited_answer: str


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


def _as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_key(chunk: object) -> str:
    filename = _as_optional_str(_read_value(chunk, ("source_filename", "filename")))
    if filename:
        return filename

    doc_id = _as_optional_str(_read_value(chunk, ("doc_id", "document_id")))
    if doc_id:
        return doc_id

    chunk_id = _as_optional_str(_read_value(chunk, ("chunk_id", "id")))
    if chunk_id:
        return chunk_id

    return "unknown_source"


def _parse_upload_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _is_stale(upload_date: str | None, threshold_days: int) -> bool:
    parsed = _parse_upload_date(upload_date)
    if parsed is None:
        return False
    return (date.today() - parsed).days > threshold_days


def _load_citation_config() -> tuple[int, int]:
    try:
        cfg = load_agents_config().citation_builder
        return cfg.staleness_threshold_days, cfg.max_citations_in_response
    except Exception as exc:
        logger.warning("[Step5a] Config load failed, using defaults: %s", exc)
        return _DEFAULT_STALENESS_THRESHOLD_DAYS, _DEFAULT_MAX_CITATIONS


def _build_cited_answer(answer_text: str, citations: list[Citation]) -> str:
    if not citations:
        return answer_text

    lines = ["", "", "---", "**Sources**"]
    lines.extend(
        f"- {citation.source_filename}"
        for citation in citations
    )
    return answer_text.rstrip() + "\n".join(lines)


def run_citation_builder(answer_text: str, chunks: list) -> CitationResult:
    """Build citations from retrieved chunk metadata.

    The LLM never supplies citation data. Missing metadata degrades to safe
    defaults so the QA endpoint can still return a response.
    """
    staleness_threshold_days, max_citations = _load_citation_config()

    if not chunks:
        return CitationResult(
            citations=[],
            citation_method="none",
            any_stale_source=False,
            ocr_sources_present=False,
            cited_answer=answer_text,
        )

    ocr_sources_present = any(
        str(_read_value(chunk, ("extraction_method",), "")).strip().lower() == "ocr"
        for chunk in chunks
    )

    grouped: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        key = _source_key(chunk)
        score = _as_float(_read_value(chunk, ("score",), 0.0))
        chunk_index = _as_int(_read_value(chunk, ("chunk_index",), None))

        existing = grouped.get(key)
        if existing is None:
            filename = _as_optional_str(_read_value(chunk, ("source_filename", "filename"))) or key
            grouped[key] = {
                "source_filename": filename,
                "page_number": _as_int(_read_value(chunk, ("page_number", "page"), None)),
                "section_heading": _as_optional_str(
                    _read_value(
                        chunk,
                        ("section_heading", "nearest_heading", "section_header", "heading"),
                    )
                ),
                "score": score,
                "category": str(_read_value(chunk, ("category", "collection"), "unknown") or "unknown"),
                "upload_date": _as_optional_str(_read_value(chunk, ("upload_date",), None)),
                "extraction_method": str(
                    _read_value(chunk, ("extraction_method",), "unknown") or "unknown"
                ),
                "chunk_indices": set(),
            }
            existing = grouped[key]
        elif score > existing["score"]:
            existing["score"] = score
            existing["page_number"] = _as_int(_read_value(chunk, ("page_number", "page"), None))
            existing["section_heading"] = _as_optional_str(
                _read_value(
                    chunk,
                    ("section_heading", "nearest_heading", "section_header", "heading"),
                )
            )
            existing["category"] = str(
                _read_value(chunk, ("category", "collection"), existing["category"])
                or existing["category"]
            )
            existing["upload_date"] = _as_optional_str(
                _read_value(chunk, ("upload_date",), existing["upload_date"])
            )
            existing["extraction_method"] = str(
                _read_value(chunk, ("extraction_method",), existing["extraction_method"])
                or existing["extraction_method"]
            )

        if chunk_index is not None:
            existing["chunk_indices"].add(chunk_index)

    ranked_items = sorted(
        grouped.values(),
        key=lambda item: float(item["score"]),
        reverse=True,
    )

    if max_citations > 0:
        ranked_items = ranked_items[:max_citations]

    citations: list[Citation] = []
    for rank, item in enumerate(ranked_items, start=1):
        score = float(item["score"])
        citations.append(
            Citation(
                rank=rank,
                source_filename=str(item["source_filename"]),
                page_number=item["page_number"],
                section_heading=item["section_heading"],
                score=score,
                score_pct=round(score * 100),
                category=str(item["category"]),
                upload_date=item["upload_date"],
                extraction_method=str(item["extraction_method"]),
                chunk_indices=sorted(item["chunk_indices"]),
            )
        )

    any_stale_source = any(
        _is_stale(citation.upload_date, staleness_threshold_days)
        for citation in citations
    )

    return CitationResult(
        citations=citations,
        citation_method="metadata" if citations else "none",
        any_stale_source=any_stale_source,
        ocr_sources_present=ocr_sources_present,
        cited_answer=_build_cited_answer(answer_text, citations),
    )
