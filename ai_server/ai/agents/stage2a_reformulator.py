"""Follow-up reformulation for retrieval-ready standalone queries."""
import logging
import re

import httpx

from ai.agents.config.agent_config_schema import LLMConfig
from ai.agents.models.context_mode import ContextModeResult
from ai.agents.models.session import SessionContext
from ai.agents.stage2_context_mode import has_case_study_signals, is_correction_challenge
from ai.config import OLLAMA_URL
from ai.config.company_profile import load_company_profile

logger = logging.getLogger(__name__)

def _build_reformulator_system_prompt() -> str:
    profile = load_company_profile()
    abbreviations = ", ".join(profile.domain.abbreviations[:5]) or (
        "internal abbreviations, process names, and system terms"
    )
    return f"""You are a query reformulation specialist for an internal document retrieval system used by {profile.company.legal_name}.

Your job is to take a vague, short, or incomplete follow-up message from a user and rewrite it as a clear, standalone question that can be answered by searching a document database.

The document database contains: SOPs, process guides, role directories, carrier and warehouse policies, claim procedures, financial operation guidelines, KPIs, escalation matrices, and historical case records - all related to the organization's operations.

---

Rules you must follow:

1. STANDALONE: The rewritten question must make complete sense to someone who has never seen the conversation. It must not reference "the previous answer", "as you mentioned", "that", "it" without replacing with the actual subject.

2. SELF-CONTAINED GUARD: Before rewriting, ask internally twice: does the current message truly need prior context? If the current message already contains its own facts, document/policy anchor, and explicit tasks, return it unchanged.

3. PRESERVE INTENT: Do not add information the user did not imply. If they said "what about the timeline?" after a question about shortage claims, rewrite to "What is the timeline for processing a freight shortage claim?" - not something broader or narrower.

4. PRESERVE CASE FACTS: Never remove case facts, IDs, quoted carrier/customer responses, numbered tasks, dates, amounts, document anchors, or requested output requirements from a self-contained case prompt.

5. PRESERVE CORRECTIONS: If the user challenges the previous answer or proposes a competing value ("isn't it August 12?", "wasn't that $999?", "I thought it was closed", "no, it was INV-123"), keep that proposed date, amount, name, ID, status, or quoted text exactly. Rewrite as a verification request, not as the original question again.

6. CONCISE: One sentence is ideal for true follow-ups. Two sentences maximum. No explanation, no preamble.

7. NO META-REFERENCES: Never include phrases like "from the previous answer", "you said earlier", "as mentioned", "based on what we discussed". Replace pronouns with the actual subject.

8. DOMAIN GROUNDING: Keep the rewritten question grounded in the organization's document terminology when the context supports it. Useful terms may include: {abbreviations}.

9. FALLBACK: If the follow-up message is completely uninterpretable even with the prior question as context, return the prior question unchanged. Do not invent a new question.

---

Output format:
Return ONLY the rewritten question as plain text.
No JSON. No quotes around it. No explanation. Just the question itself.

---

Examples of good reformulation:

Prior question: "What documents are needed for a freight shortage claim?"
Vague follow-up: "what about for theft?"
Output: What documents are required to file a freight theft claim?

Prior question: "How do I process a return authorization?"
Vague follow-up: "and the timeline?"
Output: What is the timeline for processing a return authorization?

Prior question: "Who is responsible for managing theft incidents?"
Vague follow-up: "why"
Output: Why is the theft response team responsible for managing theft incidents?

Prior question: "What are the steps for SOP-01 freight shortage processing?"
Vague follow-up: "ok explain step 3"
Output: What does step 3 of the SOP-01 freight shortage claim process involve?

Prior question: "What is the carrier response SLA for RPOD requests?"
Vague follow-up: "what if they don't respond"
Output: What happens if a carrier does not respond to an RPOD request within the SLA deadline?

Prior question: "When is the first mail date of Re: 3291474811?"
Vague follow-up: "isn't it 12th August?"
Output: Verify whether the first mail date of Re: 3291474811 is 12th August, and compare it against any other dated emails in the thread.

Prior question: "What amount was short-paid on invoice INV-7781?"
Vague follow-up: "wasn't that $999 instead?"
Output: Verify whether the short-paid amount on invoice INV-7781 is $999, and compare it against any other sourced amounts for that invoice.

Prior question: "What does RPOD mean?"
Vague follow-up: "and GR?"
Output: What does GR (Goods Receipt) mean in warehouse operations?

Prior question: "A prior answer about claims."
Current message: "Katherine Kim requested RPOD from UNIS for DO: 7256988348, Load/Pro: 17620449. Carrier Response: \"Please proceed with claims.\" Per SOP-11: 1. Confirm immediate claim filing. 2. Generate the claim package. 3. Calculate SLA compliance."
Output: Katherine Kim requested RPOD from UNIS for DO: 7256988348, Load/Pro: 17620449. Carrier Response: "Please proceed with claims." Per SOP-11: 1. Confirm immediate claim filing. 2. Generate the claim package. 3. Calculate SLA compliance.
"""


REFORMULATOR_SYSTEM_PROMPT = _build_reformulator_system_prompt()

STAGE2A_USER_TEMPLATE = """Prior user question: "{prior_query}"

Current vague follow-up: "{current_query}"

Rewrite the follow-up as a standalone retrieval question:"""

REFORMULATOR_USER_TEMPLATE = """Prior user question: "{prior_query}"

Current vague message: "{current_query}"

Rewrite the current message as a standalone retrieval question:"""


def _call_ollama_generate(user_prompt: str, system_prompt: str, config: LLMConfig) -> str:
    if config.provider.lower() != "ollama":
        raise ValueError(f"Unsupported provider for reformulator: {config.provider!r}")

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


def _strip_wrapping_quotes(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1].strip()
    return stripped


def _normalize_text_for_compare(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _rewrite_followup_query(prior_query: str, current_query: str, config: LLMConfig) -> str:
    return _call_ollama_generate(
        user_prompt=REFORMULATOR_USER_TEMPLATE.format(
            prior_query=prior_query,
            current_query=current_query,
        ),
        system_prompt=REFORMULATOR_SYSTEM_PROMPT,
        config=config,
    )


def _build_correction_query(prior_query: str, current_query: str) -> str:
    return (
        f'For the prior question "{prior_query.strip()}", verify the user\'s '
        f'proposed correction "{current_query.strip()}" against the source '
        "documents, and compare any competing dates, amounts, names, IDs, "
        "statuses, or quoted values."
    )


def run_stage2a(
    query: str,
    context_mode: ContextModeResult,
    session: SessionContext,
    config: LLMConfig,
) -> str:
    """Rewrite vague follow-ups into standalone retrieval queries."""
    if context_mode.mode != "retrieval_followup":
        logger.warning(
            "[Reformulator] Called for mode=%s; returning original query unchanged",
            context_mode.mode,
        )
        return query

    if has_case_study_signals(query):
        logger.warning("[Reformulator] Current query appears self-contained; using passthrough")
        context_mode.reformulated_query = query
        return query

    prior_query = session.last_query
    if not prior_query:
        logger.warning("[Reformulator] No prior user query available; using passthrough")
        context_mode.reformulated_query = query
        return query

    if is_correction_challenge(query):
        rewritten_query = _build_correction_query(prior_query, query)
        context_mode.reformulated_query = rewritten_query
        logger.info("[Reformulator] Correction challenge preserved for verification")
        return rewritten_query

    try:
        raw_output = _rewrite_followup_query(prior_query, query, config)
        logger.debug("[Reformulator] Raw model output: %s", raw_output)

        rewritten_query = _strip_wrapping_quotes(raw_output)
        if len(rewritten_query.split()) < 5:
            logger.warning("[Reformulator] Model output too short; using passthrough")
            rewritten_query = query
        elif _normalize_text_for_compare(rewritten_query) == _normalize_text_for_compare(query):
            logger.warning("[Reformulator] Model output matched original query; using passthrough")
            rewritten_query = query
    except Exception as exc:
        logger.warning(
            "[Reformulator] Falling back to %s after model failure: %s",
            config.fallback_behavior,
            exc,
        )
        rewritten_query = query

    context_mode.reformulated_query = rewritten_query
    return rewritten_query
