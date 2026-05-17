"""Step 3 - deterministic prompt assembly for the answering model."""
from dataclasses import dataclass

from ai.agents.config.agent_config_loader import load_agents_config
from ai.config.company_profile import load_company_profile
from ai.pipeline.prompts.format_instructions import get_format_instruction
from ai.pipeline.prompts.system_prompts import get_system_prompt
from ai.pipeline.step2_confidence_gate import ConfidenceGateResult

_ALLOWED_STYLES = {"direct", "procedural", "comparative", "exploratory"}


@dataclass
class PromptAssemblerResult:
    assembled_prompt: str
    system_prompt: str
    chunk_count_used: int
    format_instruction: str
    format_type: str
    style_used: str
    was_skipped: bool
    skip_reason: str | None
    confidence_result: ConfidenceGateResult


def _skipped_result(
    confidence_result: ConfidenceGateResult,
    skip_reason: str | None,
) -> PromptAssemblerResult:
    return PromptAssemblerResult(
        assembled_prompt="",
        system_prompt="",
        chunk_count_used=0,
        format_instruction="",
        format_type="",
        style_used="",
        was_skipped=True,
        skip_reason=skip_reason,
        confidence_result=confidence_result,
    )


def _resolve_style(raw_style: str | None, default_style: str) -> str:
    if raw_style in _ALLOWED_STYLES:
        return raw_style
    if default_style in _ALLOWED_STYLES:
        return default_style
    return "exploratory"


def _extract_chunk_text(chunk: object) -> str:
    for attr_name in ("chunk_text", "text", "content", "page_content"):
        value = getattr(chunk, attr_name, None)
        if isinstance(value, str):
            return value
    raise ValueError("Chunk object does not expose a supported text field")


def _extract_source_filenames(chunks: list) -> list[str]:
    """Return unique source filenames from chunks in first-seen order."""
    filenames: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        raw = getattr(chunk, "source_filename", None)
        if not isinstance(raw, str):
            continue
        name = raw.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        filenames.append(name)
    return filenames


def _format_string_list(items: list[str], empty_text: str = "None") -> str:
    cleaned = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    if not cleaned:
        return empty_text
    return "\n".join(f"- {item}" for item in cleaned)


def _format_tasks(tasks: list) -> str:
    if not tasks:
        return "None"

    lines: list[str] = []
    for index, task in enumerate(tasks, start=1):
        task_id = getattr(task, "id", f"task_{index}")
        task_text = getattr(task, "task_text", "")
        if task_text:
            lines.append(f"{index}. {task_id}: {task_text}")
        else:
            lines.append(f"{index}. {task_id}")
    return "\n".join(lines)


def _format_planner_context(group1_result: object) -> str:
    plan = getattr(group1_result, "retrieval_plan", None)
    if plan is None:
        return ""

    base_constraints = [
        "Use USER CASE FACTS only as facts supplied by the user.",
        "Use SOURCE DOCUMENTS only as authority for policy, procedure, requirements, timelines, thresholds, owners, and templates.",
        "Do not cite USER CASE FACTS as document evidence.",
        "If a requested task lacks source evidence, say the retrieved documents do not contain that information.",
    ]
    planner_constraints = getattr(plan, "answer_constraints", []) or []
    constraints = base_constraints + [
        item for item in planner_constraints
        if isinstance(item, str) and item.strip()
    ]

    return "\n\n".join(
        [
            "--- USER CASE FACTS ---\n"
            + _format_string_list(getattr(plan, "case_facts", []) or []),
            "--- USER TASKS ---\n"
            + _format_tasks(getattr(plan, "tasks", []) or []),
            "--- PRESERVE FOR ANSWER ---\n"
            + _format_string_list(getattr(plan, "preserve_for_answer", []) or []),
            "--- GROUNDING CONSTRAINTS ---\n"
            + _format_string_list(constraints),
        ]
    )


def run_prompt_assembler(confidence_result: ConfidenceGateResult) -> PromptAssemblerResult:
    """Build the final prompt string from a passed confidence result.

    This step is intentionally deterministic: no LLM, no network, no async.
    """
    if not confidence_result.passed:
        return _skipped_result(confidence_result, confidence_result.reason)

    try:
        group1_result = confidence_result.retrieval_result.group1_result
        raw_style = group1_result.style
        format_type = group1_result.format_type
        length_hint = group1_result.length_hint
        query_for_retrieval = group1_result.query_for_retrieval

        cfg = load_agents_config()
        prompt_cfg = cfg.prompt_assembly
        company_profile = load_company_profile()

        style_used = _resolve_style(raw_style, prompt_cfg.default_style)
        system_prompt = get_system_prompt(style_used)
        format_instruction = get_format_instruction(format_type, length_hint)

        vocabulary_block = ""
        if prompt_cfg.vocabulary_block_enabled:
            vocabulary_block = (
                "--- DOMAIN TERMINOLOGY ---\n"
                + "\n".join(company_profile.domain.abbreviations)
                + "\n--- END TERMINOLOGY ---"
            )

        planner_context_block = _format_planner_context(group1_result)

        # Style-aware chunk cap: use per-style value when configured, fall back
        # to max_chunks_in_prompt for unknown styles or missing config.
        style_cap = (
            prompt_cfg.max_chunks_by_style.get(style_used)
            or prompt_cfg.max_chunks_in_prompt
        )
        capped_chunks = confidence_result.retrieval_result.chunks[:style_cap]
        chunk_parts: list[str] = []
        for index, chunk in enumerate(capped_chunks, start=1):
            header = prompt_cfg.source_header_template.format(n=index)
            chunk_text = _extract_chunk_text(chunk)
            chunk_parts.append(f"{header}\n{chunk_text}\n")
        chunk_block = "".join(chunk_parts).rstrip("\n")

        prompt_sections: list[str] = []
        if vocabulary_block:
            prompt_sections.append(vocabulary_block)
        if planner_context_block:
            prompt_sections.append(planner_context_block)
        prompt_sections.extend(
            [
                (
                    "--- FORMAT INSTRUCTION ---\n"
                    f"{format_instruction}\n"
                    "--- END FORMAT ---"
                ),
                (
                    "--- SOURCE DOCUMENTS ---\n"
                    f"{chunk_block}\n"
                    "--- END SOURCE DOCUMENTS ---"
                ),
            ]
        )

        filenames = _extract_source_filenames(capped_chunks)
        if filenames:
            filenames_block = (
                "--- AVAILABLE SOURCE FILENAMES ---\n"
                + "\n".join(f"- {name}" for name in filenames)
                + "\n--- END SOURCE FILENAMES ---"
            )
            prompt_sections.append(filenames_block)

        prompt_sections.append(f"QUESTION: {query_for_retrieval}\n\nANSWER:")
        assembled_prompt = "\n\n".join(prompt_sections)

        return PromptAssemblerResult(
            assembled_prompt=assembled_prompt,
            system_prompt=system_prompt,
            chunk_count_used=len(capped_chunks),
            format_instruction=format_instruction,
            format_type=format_type,
            style_used=style_used,
            was_skipped=False,
            skip_reason=None,
            confidence_result=confidence_result,
        )
    except Exception:
        return _skipped_result(confidence_result, "assembler_error")
