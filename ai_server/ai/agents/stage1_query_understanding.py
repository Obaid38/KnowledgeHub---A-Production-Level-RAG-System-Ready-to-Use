"""LLM-backed query understanding with deterministic format precedence."""
import json
import logging
import re

import httpx

from ai.agents.config.agent_config_schema import LLMConfig
from ai.agents.models.domain_signal import DomainSignal
from ai.agents.models.query_understanding import QueryUnderstandingResult
from ai.config import OLLAMA_URL
from ai.config.company_profile import load_company_profile

logger = logging.getLogger(__name__)


def _format_items(items: list[str]) -> str:
    return ", ".join(items) if items else "none specified"


def _build_stage1_system_prompt() -> str:
    profile = load_company_profile()
    company = profile.company
    domain = profile.domain
    return f"""You are a query classifier for an internal enterprise document assistant used by {company.legal_name}.

About this company and its knowledge base:
{company.legal_name} uses this assistant to search internal business documents. {company.domain_summary}
Internal teams may include: {_format_items(domain.teams)}.
Systems may include: {_format_items(domain.systems)}.
Customers may include: {_format_items(domain.customers)}.
Carriers may include: {_format_items(domain.carriers)}.
Warehouse partners may include: {_format_items(domain.warehouse_partners)}.

The knowledge base may contain any of the following document types:
- Standard operating procedures (SOPs) for freight, claims, warehouse, and carrier operations
- Internal policies, compliance guidelines, and process documents
- Carrier agreements, service contracts, and vendor terms
- Financial documents including debit memos, credit records, and invoice policies
- HR and organizational guidelines
- Historical case records, claim resolutions, and incident reports
- Reference tables: KPIs, escalation matrices, abbreviation definitions, role directories

Language tolerance:
Users may write with typos, poor grammar, incomplete sentences, or non-native English. Always interpret the most plausible meaning - classify based on intent, not surface wording. Never refuse or mark out-of-domain solely because the phrasing is awkward or grammatically incorrect.

Your job:
Analyze the user's question and return a structured JSON classification.
You must respond with ONLY a valid JSON object. No explanation. No preamble. No markdown fences.

---

IN-DOMAIN definition:
A query is IN-DOMAIN if it is about ANY of the following:
- Freight operations: shipments, carriers, deliveries, shortages, returns, warehousing
- Claims: shortage claims, theft claims, damage claims, carrier claims, credit issuance
- Company processes, procedures, SOPs, workflows, or step-by-step operations
- Roles, responsibilities, team contacts, or who handles what
- Financial operations: deductions, debit memos, short-pay, invoice reconciliation, credits
- Carriers, 3PL partners, warehouse partners, or their agreements and SLAs
- Abbreviations, terminology, or definitions used in operations
- Documents, policies, compliance, or guidelines in the company knowledge base
- Historical cases, past incidents, or how similar situations were resolved
- KPIs, timelines, escalation levels, or operational targets
- Any question that references company-specific aliases, internal teams, systems, abbreviations, or similar internal terms

OUT-OF-DOMAIN definition:
A query is OUT-OF-DOMAIN ONLY when it is clearly one of:
- General knowledge questions with no business or company connection (capital cities, historical facts, science)
- Personal requests unrelated to work (jokes, stories, personal advice, creative writing)
- Questions about completely unrelated industries or topics (sports, entertainment, cooking)
- Requests that have no plausible connection to internal company documents

Important: When uncertain, classify as IN-DOMAIN. The system will handle lack of document evidence at the retrieval stage. Only refuse when clearly confident the query has no connection to company operations or documents.

---

STYLE selection rules (choose the best fit):
- "direct"       -> factual lookup, definition, who/what/when/which, single-answer questions
                   Examples: "What does RPOD mean?", "Who handles theft incidents?"
- "procedural"   -> how-to, step-by-step, process questions, sequence of actions
                   Examples: "How do I process a shortage claim?", "What are the steps for an RA?"
- "comparative"  -> comparing two or more things, X vs Y, differences, similarities
                   Examples: "What is the difference between GR and GI?", "How does one customer workflow differ from another?"
- "exploratory"  -> broad overview, general explanation, synthesis, open-ended questions
                   Examples: "Tell me about the claims process", "What should I know about reverse logistics?"

FORMAT selection rules:
- "prose"         -> use ONLY for exploratory answers (broad overviews, open-ended explanations,
                     synthesis questions). Do NOT use prose for direct factual lookups.
- "bullets"       -> use for ALL direct-style answers (factual lookups, definitions, who/what/when,
                     single-answer questions), AND when user says "list", "summarize", "key points",
                     or "overview". Direct style + prose is never correct.
- "numbered_list" -> when user says "steps", "procedure", "how to", or style=procedural
- "table"         -> when user says "in a table", "tabular", "compare as a table"
- "concise"       -> when user says "briefly", "quick", "short answer", "in one sentence"
format_is_explicit must be true only when the user literally stated a format preference.

LENGTH hint rules:
- "short"  -> user said "briefly", "quick", "short", "in one sentence", "tldr"
- "long"   -> user said "in detail", "comprehensive", "full", "explain everything", "thorough"
- "infer"  -> no explicit length stated (use this most of the time)

---

Return this exact JSON structure and nothing else:

{{
  "in_domain": true,
  "domain_confidence": "high",
  "refusal_reason": null,
  "style": "direct",
  "format_type": "bullets",
  "format_is_explicit": false,
  "length_hint": "infer"
}}

Field constraints:
- in_domain: true or false only
- domain_confidence: "high", "medium", or "low" only - NOT a number
- refusal_reason: null when in_domain is true. A short plain-English reason string when in_domain is false.
- style: "direct", "procedural", "comparative", or "exploratory" only
- format_type: "prose", "bullets", "numbered_list", "table", or "concise" only
- format_is_explicit: true or false only
- length_hint: "short", "medium", "long", or "infer" only
"""


STAGE1_SYSTEM_PROMPT = _build_stage1_system_prompt()

USER_PROMPT_TEMPLATE = """Classify this query:

"{query}"
"""

_ALLOWED_DOMAIN_CONFIDENCE = {"high", "medium", "low"}
_ALLOWED_STYLES = {"direct", "procedural", "comparative", "exploratory"}
_ALLOWED_FORMAT_TYPES = {"prose", "bullets", "numbered_list", "table", "concise"}
_ALLOWED_LENGTH_HINTS = {"short", "medium", "long", "infer"}
_CLEAR_OUT_REFUSAL = "Query does not appear to relate to company documents or operations."


def _call_ollama_generate(user_prompt: str, system_prompt: str, config: LLMConfig) -> str:
    if config.provider.lower() != "ollama":
        raise ValueError(f"Unsupported provider for query understanding: {config.provider!r}")

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
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned.strip()


def _validate_understanding_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("Query understanding payload must be a JSON object")

    required_fields = {
        "in_domain",
        "domain_confidence",
        "refusal_reason",
        "style",
        "format_type",
        "format_is_explicit",
        "length_hint",
    }
    missing_fields = sorted(required_fields - set(payload))
    if missing_fields:
        raise KeyError(", ".join(missing_fields))

    if type(payload["in_domain"]) is not bool:
        raise ValueError("'in_domain' must be a boolean")
    if payload["domain_confidence"] not in _ALLOWED_DOMAIN_CONFIDENCE:
        raise ValueError("Invalid domain_confidence")
    if payload["style"] not in _ALLOWED_STYLES:
        raise ValueError("Invalid style")
    if payload["format_type"] not in _ALLOWED_FORMAT_TYPES:
        raise ValueError("Invalid format_type")
    if type(payload["format_is_explicit"]) is not bool:
        raise ValueError("'format_is_explicit' must be a boolean")
    if payload["length_hint"] not in _ALLOWED_LENGTH_HINTS:
        raise ValueError("Invalid length_hint")

    refusal_reason = payload["refusal_reason"]
    if payload["in_domain"]:
        if refusal_reason is not None:
            raise ValueError("refusal_reason must be null for in-domain queries")
    elif not isinstance(refusal_reason, str) or not refusal_reason.strip():
        raise ValueError("refusal_reason must be a non-empty string for out-of-domain queries")

    return payload


def _apply_domain_signal_preferences(
    result: QueryUnderstandingResult,
    domain_signal: DomainSignal,
) -> QueryUnderstandingResult:
    if not domain_signal.format_is_explicit or not domain_signal.format_hint:
        return result

    result.format_is_explicit = True
    if domain_signal.format_hint == "steps":
        result.format_type = "numbered_list"
    elif domain_signal.format_hint == "bullets":
        result.format_type = "bullets"
    elif domain_signal.format_hint == "table":
        result.format_type = "table"
    elif domain_signal.format_hint == "short":
        result.format_type = "concise"
        result.length_hint = "short"
    elif domain_signal.format_hint == "long":
        result.length_hint = "long"

    return result


def _apply_style_default_format(result: QueryUnderstandingResult) -> QueryUnderstandingResult:
    """Deterministic safety net: direct-style queries always use bullets when format is not user-explicit."""
    if not result.format_is_explicit and result.style == "direct":
        result.format_type = "bullets"
    return result


def _build_default_result(
    *,
    in_domain: bool,
    domain_confidence: str,
    refusal_reason: str | None,
    classifier_method: str,
    domain_signal: DomainSignal,
) -> QueryUnderstandingResult:
    result = QueryUnderstandingResult(
        in_domain=in_domain,
        domain_confidence=domain_confidence,
        refusal_reason=refusal_reason,
        style="direct",
        format_type="prose",
        format_is_explicit=domain_signal.format_is_explicit,
        length_hint="infer",
        classifier_method=classifier_method,
    )
    return _apply_style_default_format(
        _apply_domain_signal_preferences(result, domain_signal)
    )


def run_stage1(
    query: str,
    domain_signal: DomainSignal,
    config: LLMConfig,
) -> QueryUnderstandingResult:
    """Classify the query and preserve any explicit format hints from the gate."""
    if (
        domain_signal.domain_signal == "clear_out"
        and domain_signal.gate_decision == "fast_reject"
    ):
        logger.info("[QueryUnderstanding] Skipping model call for clear out-of-domain query")
        return _build_default_result(
            in_domain=False,
            domain_confidence="high",
            refusal_reason=_CLEAR_OUT_REFUSAL,
            classifier_method="skipped_clear_out",
            domain_signal=domain_signal,
        )

    try:
        raw_output = _call_ollama_generate(
            user_prompt=USER_PROMPT_TEMPLATE.format(query=query),
            system_prompt=STAGE1_SYSTEM_PROMPT,
            config=config,
        )
        logger.debug("[QueryUnderstanding] Raw model output: %s", raw_output)

        parsed_payload = json.loads(_strip_json_fences(raw_output))
        validated_payload = _validate_understanding_payload(parsed_payload)

        result = QueryUnderstandingResult(
            in_domain=validated_payload["in_domain"],
            domain_confidence=validated_payload["domain_confidence"],
            refusal_reason=validated_payload["refusal_reason"],
            style=validated_payload["style"],
            format_type=validated_payload["format_type"],
            format_is_explicit=validated_payload["format_is_explicit"],
            length_hint=validated_payload["length_hint"],
            classifier_method="llm",
        )
        result = _apply_domain_signal_preferences(result, domain_signal)
        result = _apply_style_default_format(result)

        logger.info(
            "[QueryUnderstanding] in_domain=%s confidence=%s style=%s format=%s method=%s",
            result.in_domain,
            result.domain_confidence,
            result.style,
            result.format_type,
            result.classifier_method,
        )
        return result
    except Exception as exc:
        logger.warning(
            "[QueryUnderstanding] Falling back to %s after model failure: %s",
            config.fallback_behavior,
            exc,
        )
        return _build_default_result(
            in_domain=True,
            domain_confidence="low",
            refusal_reason=None,
            classifier_method="fallback_default",
            domain_signal=domain_signal,
        )
