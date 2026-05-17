import logging
import re
from dataclasses import dataclass, field

from ai.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DOCUMENT_TYPE_CHUNK_CONFIG,
    DOC_TYPE_HEADING_RATIO,
    DOC_TYPE_BULLET_RATIO,
    DOC_TYPE_AVG_LINE_LEN_MAX,
)

logger = logging.getLogger("knowledge_hub.chunker")

# ── Line classifiers ──────────────────────────────────────────────────────────

# Headings: multi-level numbered (1.1, 4.2.3), ALL-CAPS blocks (≥6 chars), Markdown.
# Deliberately EXCLUDES single-level steps like "1. Do X" — those are body text.
# Rule: require at least one digit after the first dot (e.g. "1.1" not "1.").
_RE_HEADING = re.compile(
    r"^("
    r"\d+\.\d[\d.]*\s+.{3,}"   # multi-level numbered: 1.1, 2.3.4 …
    r"|[A-Z][A-Z\s]{5,}"        # ALL-CAPS block heading (≥ 6 chars total)
    r"|#{1,3}\s+.{3,}"          # Markdown heading
    r")$"
)

# Bullet / list-item lines — used for doc-type detection only.
# Matches: •, -, *, –, —, ◦, ▪ starters, OR single-level numbered steps (1. / 1))
_RE_BULLET = re.compile(r"^([•\-\*◦▪–—]|\d+[\.\)]\s)\s*\S")

# Lines to skip entirely — page footers, watermarks, running headers.
# These pollute chunks but carry no semantic content.
_RE_SKIP = re.compile(
    r"^("
    r"CONFIDENTIAL.*"
    r"|INTERNAL USE ONLY.*"
    r"|©.{0,60}(Reserved|LLC|Inc|Corp|Ltd)\.?"
    r"|Page\s+\d+\s+of\s+\d+"
    r"|.{5,60}\s+(SOP|Policy|Procedure)\s+v[\d.]+"
    r"|[A-Z][A-Z\s&.,]+\s+[–—-]\s+.{5,60}(SOP|Policy|Manual|Procedure|Guidelines?)$"
    r")$",
    re.IGNORECASE,
)

# Table-of-contents entries: text followed by 4+ dots then a page number.
# Example: "3.1 Escalation Procedure ......... 12"
_RE_TOC = re.compile(r"\.{4,}\s*\d{1,3}\s*$")

# Sentence-end boundary for smarter sliding-window snapping.
_RE_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# Paragraph separator — two or more consecutive blank lines.
_RE_PARAGRAPH_BREAK = re.compile(r"\n{2,}")

# Chunks shorter than this (chars) are merged into the adjacent chunk.
_MIN_CHUNK_CHARS = 150


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ChunkResult:
    text: str              # original chunk text (NOT enriched)
    is_table: bool
    table_name: str | None
    heading: str | None    # nearest preceding heading (None for table chunks)
    chunk_index: int       # 0-based, sequential across text + table chunks
    doc_type: str = field(default="narrative")  # auto-detected: structured | list_heavy | narrative


# ── Public API ────────────────────────────────────────────────────────────────

def detect_document_type(text: str) -> str:
    """Classify text into one of three structural types by content signals.

    Returns
    -------
    "structured"  — many headings / numbered sections (SOPs, manuals, policies)
    "list_heavy"  — many bullets / short steps (procedures, checklists, agendas)
    "narrative"   — few/no headings, dense paragraphs (reports, emails, legal)

    Detection is a single O(n) pass over lines — no LLM call required.
    Thresholds are env-configurable via DOC_TYPE_* settings.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return "narrative"

    total        = len(lines)
    heading_cnt  = sum(1 for l in lines if _RE_HEADING.match(l))
    bullet_cnt   = sum(1 for l in lines if _RE_BULLET.match(l))
    avg_line_len = sum(len(l) for l in lines) / total

    heading_ratio = heading_cnt / total
    bullet_ratio  = bullet_cnt  / total

    if heading_ratio >= DOC_TYPE_HEADING_RATIO:
        return "structured"
    if bullet_ratio >= DOC_TYPE_BULLET_RATIO or avg_line_len <= DOC_TYPE_AVG_LINE_LEN_MAX:
        return "list_heavy"
    return "narrative"


def chunk_document(
    clean_text: str,
    serialized_tables: list[str],
    table_names: list[str],
    headings: list[str],  # noqa: ARG001 — reserved for future heading injection
    category: str = "general",  # kept for backward compat; no longer drives chunk size
) -> list[ChunkResult]:
    """Chunk a document into text chunks + table chunks.

    Document type is auto-detected from content signals (detect_document_type).
    The ``category`` parameter is accepted for backward compatibility but is no
    longer used to determine chunk size — auto-detection handles that.

    All chunks land in the single ``documents`` Qdrant collection; category and
    doc_type are both stored as payload fields on every point.
    """
    doc_type                  = detect_document_type(clean_text)
    chunk_size, chunk_overlap = _get_chunk_params(doc_type)

    results: list[ChunkResult] = []
    idx = 0

    # --- Text chunks ---
    text_pairs = _split_by_structure(clean_text, chunk_size, chunk_overlap)
    for chunk_text, nearest_heading in text_pairs:
        if not chunk_text.strip():
            continue
        results.append(
            ChunkResult(
                text=chunk_text,
                is_table=False,
                table_name=None,
                heading=nearest_heading,
                chunk_index=idx,
                doc_type=doc_type,
            )
        )
        idx += 1

    # --- Table chunks (never further split) ---
    for table_text, table_name in zip(serialized_tables, table_names):
        if not table_text.strip():
            continue
        results.append(
            ChunkResult(
                text=table_text,
                is_table=True,
                table_name=table_name,
                heading=None,
                chunk_index=idx,
                doc_type=doc_type,
            )
        )
        idx += 1

    logger.info(
        "[Chunker] doc_type=%s chunk_size=%d overlap=%d → %d text + %d table chunk(s)",
        doc_type,
        chunk_size,
        chunk_overlap,
        len(results) - len(serialized_tables),
        len(serialized_tables),
    )
    return results


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_chunk_params(doc_type: str) -> tuple[int, int]:
    """Return (chunk_size, chunk_overlap) for the detected document type."""
    cfg = DOCUMENT_TYPE_CHUNK_CONFIG.get(doc_type)
    if cfg:
        return int(cfg["size"]), int(cfg["overlap"])
    return CHUNK_SIZE, CHUNK_OVERLAP


def _split_by_structure(
    text: str, chunk_size: int, chunk_overlap: int
) -> list[tuple[str, str | None]]:
    """Split text into (chunk_text, nearest_heading) pairs.

    Pipeline
    --------
    1. Walk lines — skip footers / watermarks (_RE_SKIP) and TOC entries (_RE_TOC).
    2. Flush a new section on each heading line.
    3. Paragraph fallback — if no headings were detected at all, re-split the
       text on double newlines so unstructured documents get natural boundaries.
    4. Stitch — merge consecutive short sections (_stitch_short_sections) so
       tiny "4.1 Overview" / "4.2 Trigger" sub-sections don't live as isolated
       mini-chunks.
    5. Slide — sentence-aware sliding window for any section that exceeds
       chunk_size (_sliding_window).
    6. Merge — absorb any fragment < _MIN_CHUNK_CHARS into its neighbour.
    """
    lines = text.splitlines()
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_lines:   list[str]  = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            current_lines.append("")
            continue

        if _RE_SKIP.match(stripped) or _RE_TOC.search(stripped):
            continue

        if _RE_HEADING.match(stripped):
            section_text = "\n".join(current_lines).strip()
            if section_text:
                sections.append((current_heading, section_text))
            current_heading = stripped
            current_lines   = []
        else:
            current_lines.append(stripped)

    # Flush final section
    section_text = "\n".join(current_lines).strip()
    if section_text:
        sections.append((current_heading, section_text))

    # Step 3 — paragraph fallback for documents with zero heading structure
    if sections and all(h is None for h, _ in sections):
        sections = _split_by_paragraphs(text, chunk_size)

    # Step 4 — stitch consecutive short sections together
    sections = _stitch_short_sections(sections, chunk_size)

    # Step 5 — chunk each section; long ones go through sliding window
    raw_chunks: list[tuple[str, str | None]] = []
    for heading, section in sections:
        if not section:
            continue
        if len(section) <= chunk_size:
            raw_chunks.append((section, heading))
        else:
            raw_chunks.extend(_sliding_window(section, heading, chunk_size, chunk_overlap))

    # Step 6 — merge tiny tail/lead fragments into neighbours
    result:          list[tuple[str, str | None]] = []
    pending_text:    str | None = None
    pending_heading: str | None = None

    for chunk_text, heading in raw_chunks:
        if pending_text is not None:
            chunk_text      = pending_text + "\n" + chunk_text
            heading         = pending_heading
            pending_text    = None
            pending_heading = None

        if len(chunk_text.strip()) < _MIN_CHUNK_CHARS:
            pending_text    = chunk_text.strip()
            pending_heading = heading
        else:
            result.append((chunk_text, heading))

    # Flush any remaining tiny tail onto the last real chunk
    if pending_text is not None:
        if result:
            last_text, last_heading = result[-1]
            result[-1] = (last_text + "\n" + pending_text, last_heading)
        else:
            result.append((pending_text, pending_heading))

    return result


def _stitch_short_sections(
    sections: list[tuple[str | None, str]], chunk_size: int
) -> list[tuple[str | None, str]]:
    """Merge consecutive short sections to avoid tiny standalone chunks.

    A section is "short" when ``len(text) < chunk_size // 2``.
    Short sections accumulate in a buffer until the buffer would exceed
    chunk_size, then flush as one combined chunk.
    Long sections (≥ chunk_size // 2) always flush any pending buffer and
    are emitted on their own — they are natural split points.

    When multiple short sections are stitched, each subsequent heading label
    is inlined into the body text so no context is lost:

        4.1 Overview
        This procedure covers freight shortages...

        4.2 Trigger
        • Customer reports shortage via deduction...
    """
    if not sections:
        return sections

    stitch_threshold = chunk_size // 2
    result:      list[tuple[str | None, str]] = []
    buf_parts:   list[str]  = []
    buf_heading: str | None = None
    buf_len:     int        = 0

    def _flush() -> None:
        nonlocal buf_parts, buf_heading, buf_len
        if buf_parts:
            result.append((buf_heading, "\n\n".join(buf_parts)))
        buf_parts   = []
        buf_heading = None
        buf_len     = 0

    for heading, text in sections:
        # Long section — flush buffer and emit directly
        if len(text) >= stitch_threshold:
            _flush()
            result.append((heading, text))
            continue

        # Short section: inline heading label when stitching onto an existing buffer
        part     = f"{heading}\n{text}" if (heading and buf_parts) else text
        part_len = len(part)
        sep      = 2 if buf_parts else 0  # cost of the "\n\n" joiner

        if buf_parts and buf_len + sep + part_len > chunk_size:
            _flush()
            part = text  # first item in new buffer — no inline heading prefix

        if not buf_parts:
            buf_heading = heading
        buf_parts.append(part)
        buf_len += sep + part_len

    _flush()
    return result


def _split_by_paragraphs(
    text: str, chunk_size: int
) -> list[tuple[None, str]]:
    """Fallback splitter for documents with no heading structure.

    Splits on double newlines (paragraph breaks) and groups consecutive
    paragraphs into sections up to chunk_size before the sliding window.
    Paragraph boundaries are respected as natural semantic breaks.
    """
    paragraphs = [p.strip() for p in _RE_PARAGRAPH_BREAK.split(text) if p.strip()]
    if not paragraphs:
        return [(None, text.strip())] if text.strip() else []

    sections: list[tuple[None, str]] = []
    buf:      list[str] = []
    buf_len:  int       = 0

    for para in paragraphs:
        sep = 2 if buf else 0
        if buf and buf_len + sep + len(para) > chunk_size:
            sections.append((None, "\n\n".join(buf)))
            buf     = []
            buf_len = 0
        buf.append(para)
        buf_len += sep + len(para)

    if buf:
        sections.append((None, "\n\n".join(buf)))

    return sections


def _sliding_window(
    section: str, heading: str | None, chunk_size: int, chunk_overlap: int
) -> list[tuple[str, str | None]]:
    """Sentence-aware sliding window over a long section.

    Tries to snap each chunk boundary to a sentence ending within ±20% of
    chunk_size. Falls back to a hard character cut when no boundary is found.
    """
    chunks:    list[tuple[str, str | None]] = []
    start:     int = 0
    tolerance: int = chunk_size // 5  # ±20%

    while start < len(section):
        end = start + chunk_size

        if end >= len(section):
            chunk = section[start:].strip()
            if chunk:
                chunks.append((chunk, heading))
            break

        # Search for the best sentence boundary within [end-tol, end+tol]
        snap_start = max(start + 1, end - tolerance)
        snap_end   = min(len(section), end + tolerance)
        window     = section[snap_start:snap_end]

        best_boundary = -1
        for m in _RE_SENTENCE_END.finditer(window):
            candidate = snap_start + m.start() + 1
            if candidate <= end + tolerance:
                best_boundary = candidate

        if best_boundary > start:
            end = best_boundary

        chunk = section[start:end].strip()
        if chunk:
            chunks.append((chunk, heading))

        if end >= len(section):
            break
        start = end - chunk_overlap

    return chunks
