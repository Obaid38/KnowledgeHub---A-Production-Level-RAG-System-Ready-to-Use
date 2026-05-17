import logging
from dataclasses import dataclass

logger = logging.getLogger("knowledge_hub.table_serializer")

_TABLE_HEADING_KEYWORDS = {
    "table", "matrix", "list", "kpi", "categories", "stakeholder",
    "definitions", "abbreviation", "summary",
}

# Maximum character length for a single table cell before truncation.
# PDF cells with embedded paragraphs can be very long — cap them so one
# runaway cell doesn't consume the entire chunk budget.
_MAX_CELL_LEN = 200


@dataclass
class SerializedTable:
    table_name: str
    text: str       # Markdown table text
    row_count: int


def _clean_cell(cell: str) -> str:
    """Normalize a raw cell value for markdown output.

    - Collapses embedded newlines and tabs to single spaces (PDF multi-line cells)
    - Strips leading/trailing whitespace
    - Truncates to _MAX_CELL_LEN to prevent runaway cell text
    - Escapes pipe characters so the markdown table is not broken
    """
    cleaned = " ".join(cell.split())         # collapses \n, \t, multiple spaces
    if len(cleaned) > _MAX_CELL_LEN:
        cleaned = cleaned[:_MAX_CELL_LEN - 3] + "..."
    return cleaned.replace("|", "/")         # pipe inside a cell breaks markdown syntax


def detect_table_names_from_headings(
    headings: list[str], table_count: int
) -> list[str]:
    """Return up to table_count names from headings that look table-related,
    filling remaining slots with generic 'Table N' labels."""
    candidates = [
        h for h in headings
        if any(kw in h.lower() for kw in _TABLE_HEADING_KEYWORDS)
    ]
    names: list[str] = []
    for i in range(table_count):
        names.append(candidates[i] if i < len(candidates) else f"Table {i + 1}")
    return names


def serialize_tables(
    raw_tables: list[list[list[str]]],
    table_names: list[str] | None = None,
) -> list[SerializedTable]:
    """Convert raw table row arrays into markdown-formatted text blocks.

    Output format:
        <Table Name>

        | Col1 | Col2 | Col3 |
        |---|---|---|
        | val  | val  | val  |
        ...

    This is better than the previous NL key-value sentence format because:
    - PDF cells with embedded newlines are collapsed to spaces (no mid-sentence breaks)
    - BM25 term frequency fires on exact values without prose wrappers
    - LLMs read markdown tables reliably and can extract any column directly
    - Empty and None cells are handled uniformly
    """
    result: list[SerializedTable] = []

    for idx, table in enumerate(raw_tables):
        if len(table) < 2:
            # No data rows beyond a header — skip
            continue

        name = (
            table_names[idx]
            if table_names and idx < len(table_names)
            else f"Table {idx + 1}"
        )

        # Build header row — fill blank header cells with Column N
        raw_headers = [_clean_cell(str(c)) for c in table[0]]
        col_count = len(raw_headers)
        headers = [
            h if h else f"Column {i + 1}"
            for i, h in enumerate(raw_headers)
        ]

        lines: list[str] = [
            name,
            "",
            "| " + " | ".join(headers) + " |",
            "|" + "|".join(["---"] * col_count) + "|",
        ]

        data_row_count = 0
        for row in table[1:]:
            # Normalize row length to match header width
            padded = list(row) + [""] * max(0, col_count - len(row))
            cells = [_clean_cell(str(c)) for c in padded[:col_count]]

            # Skip fully empty rows
            if not any(cells):
                continue

            data_row_count += 1
            lines.append("| " + " | ".join(cells) + " |")

        serialized_text = "\n".join(lines)
        logger.info("[TableSerializer] %s: %d data rows serialized", name, data_row_count)
        result.append(
            SerializedTable(
                table_name=name,
                text=serialized_text,
                row_count=data_row_count,
            )
        )

    return result
