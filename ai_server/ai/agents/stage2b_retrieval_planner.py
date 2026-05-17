"""Stage 2b - retrieval planning for multi-query RAG.

This agent does not answer the user. It separates user-provided case facts from
document evidence needs and produces bounded retrieval subqueries.
"""
import json
import logging
import re
from typing import Any

import httpx

from ai.agents.config.agent_config_schema import LLMConfig
from ai.agents.models.retrieval_plan import (
    PlannerRetrievalQuery,
    PlannerTask,
    RetrievalPlanResult,
)
from ai.config import OLLAMA_URL
from ai.config.company_profile import load_company_profile

logger = logging.getLogger(__name__)

_MAX_RETRIEVAL_QUERIES = 6
_ALLOWED_PRIORITIES = {"high", "medium", "low"}


def _example_carrier() -> str:
    profile = load_company_profile()
    return profile.domain.carriers[0] if profile.domain.carriers else "Carrier"


RETRIEVAL_PLANNER_SYSTEM_PROMPT = f"""You are a retrieval planning agent for an enterprise document-grounded QA system.

Your job is to transform the user message into a retrieval plan.
Do not answer the user.
Do not make policy conclusions.
Do not use outside knowledge.
Return only valid JSON matching the required schema.

A user message may contain:
- background facts or a short case study
- quoted emails or operational notes
- one or more tasks/questions
- document anchors such as SOP names, policy names, teams, forms, carriers, deadlines, or process names
- opaque case identifiers such as invoice numbers, claim numbers, load IDs, BOLs, DOs, ticket IDs, or dates

Your core responsibility:
Separate USER-PROVIDED FACTS from DOCUMENT EVIDENCE NEEDS.

Rules:
1. User-provided facts are inputs to preserve for answering. They are not source evidence.
2. Retrieval queries should search for policies, procedures, required documents, timelines, thresholds, owners, templates, examples, and escalation rules.
3. Do not retrieve opaque identifiers by default. Preserve IDs like BOL, invoice, load ID, claim ID, DO, PO, ticket ID, and exact dates unless the user explicitly asks to find that exact record.
4. Exact-record exception: when the user asks about a specific record, email thread, claim, invoice, order, shipment, ticket, document reference, or proposed correction, include the exact identifier and proposed value in at least one retrieval query.
5. For exact-record lookups, prefer record/evidence documents over SOP or policy documents unless the user also asks for process, policy, owner, timeline, or compliance rules.
6. Use exact anchors when they are likely document anchors, such as SOP names, process names, forms, teams, carriers, deadlines, thresholds, and workflow names.
7. Decompose by task, not by every sentence.
8. For simple one-part questions, usually produce one retrieval query.
9. For procedural questions, usually produce 2-3 retrieval queries.
10. For case-application prompts, usually produce 3-4 retrieval queries.
11. For comparison prompts, usually produce one query per compared item plus one general comparison query.
12. Avoid answer-like conclusions. Do not say "this is Level 3." Instead retrieve escalation threshold evidence.
13. Keep retrieval queries short, specific, and searchable.
14. If the user asks multiple numbered tasks, every task must be represented in tasks.
15. If a fact should appear in the final answer but should not be searched as authority, put it in preserve_for_answer.
16. If a fact should explicitly not become a retrieval query, put it in do_not_retrieve.

Return this exact JSON structure:

{
  "case_context_present": true,
  "case_facts": [],
  "tasks": [
    {
      "id": "task_1",
      "task_text": "",
      "evidence_needed": []
    }
  ],
  "retrieval_queries": [
    {
      "id": "q1",
      "task_ids": ["task_1"],
      "query": "",
      "priority": "high"
    }
  ],
  "preserve_for_answer": [],
  "do_not_retrieve": [],
  "answer_constraints": []
}

Example 1: case-study prompt

User:
The following has been reported:
- Load ID / BOL: 17847773
- Carrier: {_example_carrier()}
- Status: "The entire trailer was stolen so no units have been returned or will be returning to the WH."
- Carrier account manager states: "We will file the claim with the carrier and insurance. Please ensure the claim package is submitted ASAP."

Per SOP-02:
1. List all required notifications.
2. Compile the incident detail template.
3. Since the entire trailer was stolen, confirm the process.
4. Generate the claim submission package for the carrier.
5. Set up tracking milestones.

Output:
{
  "case_context_present": true,
  "case_facts": [
    "Load ID / BOL: 17847773",
    "Carrier: {_example_carrier()}",
    "The entire trailer was stolen",
    "No units have been returned or are expected to return to the warehouse",
    "Carrier account manager says the claim will be filed with the carrier and insurance",
    "Carrier account manager asks for the claim package ASAP"
  ],
  "tasks": [
    {
      "id": "task_1",
      "task_text": "List all required notifications",
      "evidence_needed": ["SOP-02 theft incident notification recipients and stakeholders"]
    },
    {
      "id": "task_2",
      "task_text": "Compile the incident detail template",
      "evidence_needed": ["SOP-02 theft incident claim package or incident detail required fields"]
    },
    {
      "id": "task_3",
      "task_text": "Confirm the process for an entire trailer theft",
      "evidence_needed": ["SOP-02 full trailer theft workflow and no-return/full-claim handling"]
    },
    {
      "id": "task_4",
      "task_text": "Generate the claim submission package for the carrier",
      "evidence_needed": ["SOP-02 claim submission package requirements and any carrier-specific process"]
    },
    {
      "id": "task_5",
      "task_text": "Set up tracking milestones",
      "evidence_needed": ["SOP-02 theft incident timeline, immediate notification, and 24-hour claim submission"]
    }
  ],
  "retrieval_queries": [
    {
      "id": "q1",
      "task_ids": ["task_1"],
      "query": "SOP-02 theft incident required notifications internal stakeholders carrier escalation",
      "priority": "high"
    },
    {
      "id": "q2",
      "task_ids": ["task_2", "task_4"],
      "query": "SOP-02 theft incident claim package incident detail required fields claim submission package",
      "priority": "high"
    },
    {
      "id": "q3",
      "task_ids": ["task_3"],
      "query": "SOP-02 full trailer theft no units returned proceed directly with full claim",
      "priority": "high"
    },
    {
      "id": "q4",
      "task_ids": ["task_5"],
      "query": "SOP-02 theft incident timeline immediate notification 24-hour claim submission",
      "priority": "high"
    }
  ],
  "preserve_for_answer": [
    "Load ID / BOL: 17847773",
    "Carrier: {_example_carrier()}",
    "Entire trailer stolen",
    "No units returned or expected to return",
    "Carrier account manager says the claim will be filed with the carrier and insurance"
  ],
  "do_not_retrieve": [
    "17847773"
  ],
  "answer_constraints": [
    "Use case facts as user-provided inputs, not source evidence",
    "Use retrieved documents as authority for required notifications, package requirements, workflow, and timeline",
    "Do not cite user-provided case facts as source evidence",
    "If carrier-specific instructions are not found in sources, state that the retrieved sources do not specify them"
  ]
}

Example 2: simple prompt

User:
What are the escalation levels in the SOP, and when should each level be triggered?

Output:
{
  "case_context_present": false,
  "case_facts": [],
  "tasks": [
    {
      "id": "task_1",
      "task_text": "List escalation levels and when each level should be triggered",
      "evidence_needed": ["escalation levels, trigger conditions, actions, and timelines from the SOP"]
    }
  ],
  "retrieval_queries": [
    {
      "id": "q1",
      "task_ids": ["task_1"],
      "query": "escalation levels trigger conditions action timeline escalation matrix SOP",
      "priority": "high"
    }
  ],
  "preserve_for_answer": [],
  "do_not_retrieve": [],
  "answer_constraints": [
    "Answer only from retrieved escalation evidence",
    "Do not invent missing escalation levels or trigger conditions"
  ]
}
"""

RETRIEVAL_PLANNER_USER_TEMPLATE = """Final standalone user message:
\"\"\"
{query}
\"\"\"

Return retrieval plan JSON:"""


def _call_ollama_generate(user_prompt: str, system_prompt: str, config: LLMConfig) -> str:
    if config.provider.lower() != "ollama":
        raise ValueError(f"Unsupported provider for retrieval planner: {config.provider!r}")

    response = httpx.post(
        f"{OLLAMA_URL}/v1/chat/completions",
        json={
            "model": config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        },
        timeout=float(config.timeout_seconds),
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"Ollama returned no choices: {payload!r}")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    output = message.get("content") if isinstance(message, dict) else None
    if not isinstance(output, str) or not output.strip():
        raise ValueError(f"Ollama returned no response text: {payload!r}")
    return output


def _strip_json_fences(raw_text: str) -> str:
    cleaned = raw_text.strip()
    # Strip <think>...</think> blocks emitted by reasoning models (e.g. qwen3).
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned.strip()


def _as_string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _validate_tasks(value: Any) -> list[PlannerTask]:
    if not isinstance(value, list):
        raise ValueError("tasks must be a list")

    tasks: list[PlannerTask] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("id") or f"task_{index}").strip()
        task_text = str(item.get("task_text") or "").strip()
        evidence_needed = _as_string_list(
            item.get("evidence_needed", []),
            field_name=f"tasks[{index}].evidence_needed",
        )
        if not task_text:
            continue
        tasks.append(
            PlannerTask(
                id=task_id or f"task_{index}",
                task_text=task_text,
                evidence_needed=evidence_needed,
            )
        )
    return tasks


def _validate_retrieval_queries(value: Any) -> list[PlannerRetrievalQuery]:
    if not isinstance(value, list):
        raise ValueError("retrieval_queries must be a list")

    queries: list[PlannerRetrievalQuery] = []
    seen_queries: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        query_text = str(item.get("query") or "").strip()
        normalized = re.sub(r"\s+", " ", query_text.casefold())
        if not query_text or normalized in seen_queries:
            continue
        seen_queries.add(normalized)

        priority = str(item.get("priority") or "medium").strip().lower()
        if priority not in _ALLOWED_PRIORITIES:
            priority = "medium"

        query_id = str(item.get("id") or f"q{index}").strip()
        queries.append(
            PlannerRetrievalQuery(
                id=query_id or f"q{index}",
                task_ids=_as_string_list(
                    item.get("task_ids", []),
                    field_name=f"retrieval_queries[{index}].task_ids",
                ),
                query=query_text,
                priority=priority,
            )
        )
        if len(queries) >= _MAX_RETRIEVAL_QUERIES:
            break
    return queries


def _validate_plan_payload(payload: object, raw_output: str) -> RetrievalPlanResult:
    if not isinstance(payload, dict):
        raise ValueError("Retrieval planner payload must be a JSON object")

    required_fields = {
        "case_context_present",
        "case_facts",
        "tasks",
        "retrieval_queries",
        "preserve_for_answer",
        "do_not_retrieve",
        "answer_constraints",
    }
    missing_fields = sorted(required_fields - set(payload))
    if missing_fields:
        raise KeyError(", ".join(missing_fields))

    if type(payload["case_context_present"]) is not bool:
        raise ValueError("case_context_present must be a boolean")

    tasks = _validate_tasks(payload["tasks"])
    retrieval_queries = _validate_retrieval_queries(payload["retrieval_queries"])
    if not retrieval_queries:
        raise ValueError("retrieval_queries must contain at least one valid query")

    return RetrievalPlanResult(
        case_context_present=payload["case_context_present"],
        case_facts=_as_string_list(payload["case_facts"], field_name="case_facts"),
        tasks=tasks,
        retrieval_queries=retrieval_queries,
        preserve_for_answer=_as_string_list(
            payload["preserve_for_answer"],
            field_name="preserve_for_answer",
        ),
        do_not_retrieve=_as_string_list(
            payload["do_not_retrieve"],
            field_name="do_not_retrieve",
        ),
        answer_constraints=_as_string_list(
            payload["answer_constraints"],
            field_name="answer_constraints",
        ),
        planner_method="llm",
        raw_output=raw_output,
    )


def build_fallback_plan(query: str, *, method: str = "fallback_passthrough") -> RetrievalPlanResult:
    """Return a safe single-query plan when the planner cannot be used."""
    return RetrievalPlanResult(
        case_context_present=False,
        case_facts=[],
        tasks=[
            PlannerTask(
                id="task_1",
                task_text=query.strip() or "Answer the user question",
                evidence_needed=["Relevant document evidence for the user question"],
            )
        ],
        retrieval_queries=[
            PlannerRetrievalQuery(
                id="q1",
                task_ids=["task_1"],
                query=query.strip(),
                priority="high",
            )
        ],
        preserve_for_answer=[],
        do_not_retrieve=[],
        answer_constraints=[
            "Answer only from retrieved document evidence",
            "Do not invent missing requirements, timelines, thresholds, owners, or procedures",
        ],
        planner_method=method,
        raw_output=None,
    )


def run_stage2b(query: str, config: LLMConfig) -> RetrievalPlanResult:
    """Build a retrieval plan for the final standalone user query."""
    if not query.strip():
        return build_fallback_plan(query, method="fallback_empty_query")

    try:
        raw_output = _call_ollama_generate(
            user_prompt=RETRIEVAL_PLANNER_USER_TEMPLATE.format(query=query),
            system_prompt=RETRIEVAL_PLANNER_SYSTEM_PROMPT,
            config=config,
        )
        logger.debug("[RetrievalPlanner] Raw model output: %s", raw_output)
        parsed_payload = json.loads(_strip_json_fences(raw_output))
        result = _validate_plan_payload(parsed_payload, raw_output)
        logger.info(
            "[RetrievalPlanner] method=llm case_context=%s tasks=%d queries=%d",
            result.case_context_present,
            len(result.tasks),
            len(result.retrieval_queries),
        )
        return result
    except Exception as exc:
        logger.warning(
            "[RetrievalPlanner] Falling back to single-query plan after failure: %s",
            exc,
        )
        return build_fallback_plan(query)
