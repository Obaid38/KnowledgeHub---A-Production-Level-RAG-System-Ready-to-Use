"""Format instructions for deterministic Step 3 prompt assembly."""

_DEFAULT_INSTRUCTION = "Respond clearly and concisely. Use the format that best fits the content."
_NUMBERED_LIST_INSTRUCTION = (
    "Respond as a numbered list. Each item should be a distinct, complete step or\n"
    "point. Number from 1. If a step has a sub-condition, indent it under the\n"
    "parent step."
)
_TABLE_INSTRUCTION = (
    "Respond using a markdown table. Include clear column headers. Each row should\n"
    "represent one distinct item, option, or data point. If a table does not fit\n"
    "the content (e.g., a single factual answer), use prose instead and note why."
)
_CONCISE_INSTRUCTION = (
    "Respond in 1–3 sentences maximum. State only the single most important fact\n"
    "or answer. Do not add context, background, or caveats unless they are critical\n"
    "to understanding the answer."
)

_FORMAT_INSTRUCTIONS = {
    ("prose", "short"): (
        "Write 2–3 focused paragraphs. Cover the key point and essential supporting\n"
        "detail. Stop when the answer is complete — do not pad.\n"
        "Use bullet points for any list of three or more items (documents, teams,\n"
        "carriers, steps, thresholds) — do not embed them as run-on sentences."
    ),
    ("prose", "long"): (
        "Write in full paragraphs with as much detail as the source documents support.\n"
        "Use headers (## or bold) to organize sections if the topic has multiple distinct areas.\n"
        "Use bullet points for any list of three or more items (documents, teams,\n"
        "carriers, steps, thresholds) — do not embed them as run-on sentences.\n"
        "Prioritize completeness and clarity over brevity."
    ),
    ("prose", "infer"): (
        "Write in paragraph form with clear structure. Use headers (## or bold) to\n"
        "separate distinct sub-topics when the answer covers multiple areas.\n"
        "Use bullet points for any list of three or more items (required documents,\n"
        "teams, carriers, steps, thresholds, or conditions) — do not embed long lists\n"
        "as run-on sentences inside paragraphs. Let the content dictate the length:\n"
        "a simple factual question warrants 1–2 paragraphs, a broad topic warrants more."
    ),
    ("bullets", "short"): (
        "Respond using bullet points. Keep each bullet to one clear, complete idea.\n"
        "Use no more than 6–8 bullets total."
    ),
    ("bullets", "long"): (
        "Respond using bullet points. Cover all relevant points from the sources.\n"
        "Group related bullets under bold sub-headers if there are more than 6 items."
    ),
    ("bullets", "infer"): (
        "Respond using bullet points. Each bullet should be one clear, complete idea.\n"
        "Use as many bullets as the content requires — neither pad nor truncate."
    ),
}


def get_format_instruction(format_type: str, length_hint: str) -> str:
    """Return the output-format instruction for a format/length combination."""
    if format_type == "numbered_list":
        return _NUMBERED_LIST_INSTRUCTION
    if format_type == "table":
        return _TABLE_INSTRUCTION
    if format_type == "concise":
        return _CONCISE_INSTRUCTION
    return _FORMAT_INSTRUCTIONS.get((format_type, length_hint), _DEFAULT_INSTRUCTION)
