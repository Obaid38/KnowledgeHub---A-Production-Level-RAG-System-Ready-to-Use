"""Conversation context classification with regex-first routing."""
import json
import logging
import re

import httpx

from ai.agents.config.agent_config_schema import LLMConfig
from ai.agents.models.context_mode import ContextModeResult
from ai.agents.models.query_understanding import QueryUnderstandingResult
from ai.agents.models.session import SessionContext
from ai.agents.stage0_domain_gate import STRONG_IN_TERMS
from ai.config import OLLAMA_URL
from ai.config.company_profile import load_company_profile

logger = logging.getLogger(__name__)

TRANSFORM_PATTERNS = [
    # --- Explicit length/style adjustments ---
    # "make it shorter", "make that more concise"
    r"^\s*(make it|make that)\s+(shorter|longer|simpler|more concise|more detailed)\b",

    # Standalone reformat verbs with optional pronoun: "simplify", "summarize it"
    r"^\s*(simplify|summarize|summarise|shorten|expand|elaborate)\s*(it|that|this)?\s*$",

    # --- Pure format-switch phrases ---
    # "in bullets", "as a list", "as a table", "as numbered" — allow trailing ?
    r"^\s*(in bullet(s| points)?|as bullets?|as a (numbered )?list|as a table|as numbered)\s*\??\s*$",

    # "translate that to Spanish" etc.
    r"^\s*(translate (that|it|this) to)\b",

    # Length complaints: "too long", "too short", "too technical"
    r"^\s*(too long|too short|too technical|too simple|too wordy|too verbose)\s*$",

    # TL;DR shorthand
    r"^\s*(tldr|tl;dr)\s*$",

    # Paraphrase verbs: "reword it", "rephrase that"
    r"^\s*(reword|rephrase|rewrite)\s*(it|that|this)?\s*$",

    # "give me the short version", "give me a concise version"
    r"^\s*(give me (the )?(short|brief|quick|concise) version)\b",

    # Plain-language request: "in plain English", "in simple terms"
    r"\b(in (plain|simple|plain english|layman))\s*(terms|language|english)?\b",

    # --- Verb-pronoun-preposition-format patterns (previously missing) ---
    # "put it in bullet points", "Can you put that in a list", "format it as a table"
    # "convert this into a numbered list", "turn that into bullets"
    # FORMAT anchored to specific terms to prevent false positives.
    r"^\s*(can you\s+)?(put|format|convert|turn|change)\s+(it|that|this)\s+(in(to)?|as|to)\s+(bullet(s| points)?|a (numbered )?list|a table|numbered list)\b",

    # "make it into bullets", "make that a table", "make this a numbered list"
    r"^\s*(make (it|that|this))\s+(into\s+)?(bullet(s| points)?|a (numbered )?list|a table|numbered list)\b",

    # "show it as bullets", "display that as a table", "present this as a list"
    r"^\s*(show|display|present|render)\s+(it|that|this)\s+(as|in)\s+(bullet(s| points)?|a (numbered )?list|a table)\b",
]

FOLLOWUP_PATTERNS = [
    r"^\s*(why|how|what|when|where|who)\s*\??\s*$",
    r"^\s*(ok|okay)\s*,?\s*(explain|go on|continue|and|but|so)\b",
    r"^\s*(then what|what then|what next|and then)\b",
    r"^\s*(tell me more|give me more|more detail|more info|more information)\b",
    r"^\s*(what about|how about|what if|but what|and what)\b",
    r"^\s*(compare (that|it|this|them))\b",
    r"^\s*(explain (that|it|this|why|how))\b",
    r"^\s*(go (deeper|further|on))\b",
    r"^\s*(i (don.t understand|need more|want to know more))\b",
    r"^\s*(it|that|this|they|those|these)\s+(is|are|means|seems|looks|works)\b",
]

CITATION_INTENT_PATTERNS = [
    # Direct page/location questions
    r"\bwhat page\b",
    r"\bwhich page\b",
    r"\bpage number\b",
    r"\bon what page\b",
    r"\bwhat page (number|was|is|did)\b",

    # Section / heading questions
    r"\bwhat section\b",
    r"\bwhich section\b",
    r"\bwhat heading\b",
    r"\bwhich heading\b",
    r"\bunder what (section|heading)\b",
    r"\bin which section\b",

    # Document / source / file questions
    r"\bwhat document\b",
    r"\bwhich document\b",
    r"\bwhat source\b",
    r"\bwhich source\b",
    r"\bwhat file\b",
    r"\bwhich file\b",
    r"\bwhere (did|does) (that|this|it) come from\b",
    r"\bwhere (was|is) (that|this|it) (from|found|mentioned|written|stated|located)\b",
    r"\bwhere (can i|can we|do i|do we) find (that|this)\b",

    # Source count / multiple sources
    r"\bhow many sources\b",
    r"\bhow many documents\b",
    r"\bwhere did you (get|find|source|pull)\b",
    r"\bwhat (is|was) the source\b",
    r"\bcan you (tell|show) me (the |your )source\b",
    r"\b(show|list|give|provide) (me )?(the |your )?(sources?|references?|citations?)\b",
    r"\bwhat (are|were) (my |the |your )?(sources?|references?|citations?)\b",
]

CORRECTION_CHALLENGE_PATTERNS = [
    # "isn't it Aug 12?", "wasn't that $999?", "are those closed?"
    r"^\s*(isn'?t|is not|wasn'?t|was not|weren'?t|were not|aren'?t|are not)\s+"
    r"(it|that|this|they|those|these)\b",
    # "shouldn't it be Aug 12?", "wouldn't that have been closed?"
    r"^\s*(shouldn'?t|should not|wouldn'?t|would not|couldn'?t|could not)\s+"
    r"(it|that|this|they|those|these)\s+(be|have been)\b",
    # "are you sure?", "sure about that?"
    r"^\s*(are|were|was|is)\s+you\s+sure\b",
    r"^\s*sure\s+about\s+(it|that|this|those|these|them)\b",
    # "I think it was Aug 12", "I thought that amount was $999"
    r"^\s*i\s+(think|thought|believe|believed|remember|recall)\s+"
    r"((it|that|this|they|those|these)\s+)?"
    r"(is|was|were|are|should be|should have been)\b",
    # "no, it was Aug 12", "actually $999", "correction: Aug 12"
    r"^\s*(no|nah|actually|correction|rather|instead)\b",
]

def _build_context_system_prompt() -> str:
    profile = load_company_profile()
    return f"""You are a conversation mode classifier for an internal document assistant used by {profile.company.legal_name}.

Your only job is to classify how the current user message relates to the conversation history, so the system knows how to respond correctly.

---

COMPLETENESS TEST — apply this before choosing any mode:
Ask yourself: "If I deleted the entire prior conversation, would this message still make sense as a search query?"
If YES → it is "standalone". Do not override this with any other reasoning.
A message that names its own subject (a role, team, process, term, acronym, document type, person, company, or specific domain concept) passes this test and is always "standalone".

---

There are exactly four modes:

MODE A - "standalone"
The message is self-contained. It can be understood, searched, and answered without any knowledge of prior conversation.
Use this when the message:
- Names a specific entity, process, role, document type, or domain term
- Forms a grammatically complete question or instruction on its own
- Could have been typed as a first message in a fresh conversation
Also use this for self-contained operational case prompts that include facts, document references, and tasks, even if a prior conversation exists.

IMPORTANT: A question about the same topic as the prior answer is still "standalone" if it is a complete, searchable question. Topic overlap does not make a message a followup. Only dependency on the prior answer makes it a followup.

MODE B - "answer_transform"
The user ONLY wants to change the format or presentation of the previous answer.
No new information is needed. No retrieval required.
Use this ONLY when you are fully certain the user is asking for nothing new — only a reshape of what was already said.
Examples: "make it shorter", "put that in bullets", "simplify it", "too long", "in plain English", "give me the tldr".
CRITICAL: If the message references any specific topic, entity, or domain term beyond just reformatting instructions, do NOT use this mode.

MODE C - "retrieval_followup"
ONLY use this when the message is genuinely INCOMPLETE — it cannot be understood or retrieved without reading the prior answer.
The message must be a fragment, a dangling pronoun reference, or a vague continuation with no self-contained subject.
Ask: "What would I search for if I had never seen the prior answer?" If the answer is "I don't know — the subject is missing", then it is retrieval_followup.
Prototypical retrieval_followup messages: a single word ("why?", "how?"), a fragment ("what about that?", "and then?"), or a question whose subject is an unresolved pronoun ("what if they don't?", "explain that part", "tell me more").
Also use retrieval_followup for short correction or challenge messages that depend on the previous answer, such as "isn't it August 12?", "wasn't that $999?", "are you sure?", or "I thought it was closed." These are verification requests; the proposed value must be preserved downstream.

CRITICAL: If the message contains a named entity, acronym, role, process name, document reference, or any specific domain term, it is NOT retrieval_followup — it is standalone. The subject is already present; no prior context is needed to search for it.
CRITICAL: A complete grammatical question is NEVER retrieval_followup, even if the topic overlaps with the prior answer.
CRITICAL: A correction/challenge message is different from a normal complete question: keep the user's proposed date, amount, name, ID, status, or quoted text intact.
CRITICAL: A false retrieval_followup triggers a reformulator that injects prior context into a complete query, corrupting it. The cost of a wrong retrieval_followup is high. When in doubt, use "standalone".

MODE D - "citation_lookup"
The user ONLY wants to know where the previous answer came from — the source document, page, section, or file.
No new retrieval is needed. No new information is being requested.
Use this ONLY when the user is asking about provenance of the prior answer, not asking for more information on the topic.
Examples: "what page was that on?", "which document was that from?", "show me your sources", "where did you get that?", "list citations".

---

Decision rules you must follow:
1. Always run the COMPLETENESS TEST first. A message that passes it is "standalone" — no other rule overrides this.
2. Default to "standalone" when uncertain. Standalone is always safe; retrieval_followup is risky.
3. Only use "answer_transform" when the message contains zero domain content — only formatting instructions.
4. When torn between "answer_transform" and "retrieval_followup", choose "retrieval_followup".
5. When torn between "standalone" and "retrieval_followup", always choose "standalone".
6. Only use "retrieval_followup" when the message has no self-contained subject — it is incomplete as a search query.
7. Only use "citation_lookup" for explicit provenance/source questions about the prior answer.
8. Topic similarity to the prior answer is NOT evidence of retrieval_followup. Only incompleteness is.

---

Examples:

Previous assistant answer: "An answer containing some information about a process."
Current user message: "A long operational case prompt with reported facts, document reference numbers, carrier responses, and numbered tasks."
Output: {{"mode":"standalone","confidence":"high","reasoning":"Self-contained case prompt with its own facts, document anchor, and tasks."}}

Previous assistant answer: "An answer about a topic X."
Current user message: "A complete question that fully names its subject and makes sense independently, even though it is on the same topic as the prior answer."
Output: {{"mode":"standalone","confidence":"high","reasoning":"Complete self-contained question — passes completeness test regardless of topic overlap."}}

Previous assistant answer: "An answer about topic X."
Current user message: "what if they do not respond?"
Output: {{"mode":"retrieval_followup","confidence":"high","reasoning":"Fragment with unresolved pronoun — cannot be searched without prior context."}}

Previous assistant answer: "An answer about topic X."
Current user message: "why?"
Output: {{"mode":"retrieval_followup","confidence":"high","reasoning":"Single-word fragment with no subject — incomplete without prior context."}}

Previous assistant answer: "The first record date is August 25."
Current user message: "isn't it August 12?"
Output: {{"mode":"retrieval_followup","confidence":"high","reasoning":"Correction challenge that needs prior subject and must preserve the proposed date."}}

Previous assistant answer: "An answer about some process."
Current user message: "put that in bullets"
Output: {{"mode":"answer_transform","confidence":"high","reasoning":"Pure formatting instruction with no domain content."}}

Previous assistant answer: "An answer with cited sources."
Current user message: "what document did that come from?"
Output: {{"mode":"citation_lookup","confidence":"high","reasoning":"User is asking for provenance of prior answer only."}}

---

You must respond with ONLY a valid JSON object. No explanation. No preamble. No markdown.

Return this exact structure:

{{
  "mode": "standalone",
  "confidence": "high",
  "reasoning": "One short sentence explaining your decision."
}}

Field constraints:
- mode: "standalone", "answer_transform", "retrieval_followup", or "citation_lookup" only
- confidence: "high", "medium", or "low" only
- reasoning: plain English, one sentence, under 20 words
"""


CONTEXT_SYSTEM_PROMPT = _build_context_system_prompt()

STAGE2_USER_TEMPLATE = """Previous assistant answer (may be truncated):
\"\"\"{prior_answer_summary}\"\"\"

Current user message:
"{current_query}"

What mode is this? Return only the JSON."""

CONTEXT_MODE_USER_TEMPLATE = """Previous assistant answer (summarized):
"{prior_answer_summary}"

Current user message:
"{current_query}"

What mode is this?"""

_TRANSFORM_REGEXES = [re.compile(pattern, re.IGNORECASE) for pattern in TRANSFORM_PATTERNS]
_FOLLOWUP_REGEXES = [re.compile(pattern, re.IGNORECASE) for pattern in FOLLOWUP_PATTERNS]
_CITATION_REGEXES = [re.compile(pattern, re.IGNORECASE) for pattern in CITATION_INTENT_PATTERNS]
_CORRECTION_REGEXES = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in CORRECTION_CHALLENGE_PATTERNS
]
_TRANSFORM_PREFIX_REGEX = re.compile(
    r"^\s*(simplify|summarize|summarise|shorten|expand|elaborate|reword|rephrase|rewrite)\b",
    re.IGNORECASE,
)
_ALLOWED_MODES = {"standalone", "answer_transform", "retrieval_followup", "citation_lookup"}
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}
_FOLLOWUP_PRONOUNS = {"it", "that", "this", "they", "those", "these", "them"}
_VERB_HINTS = {
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "can",
    "should",
    "would",
    "will",
    "handle",
    "handling",
    "process",
    "processing",
    "compare",
    "mean",
    "means",
    "need",
    "required",
    "explain",
}
_DOCUMENT_ANCHOR_REGEX = re.compile(
    r"\bper\s+(?:SOP|policy|procedure|guide|guideline|manual|document|contract|agreement)"
    r"[-\s:#A-Za-z0-9]*",
    re.IGNORECASE,
)
_NUMBERED_TASK_REGEX = re.compile(
    r"(?:^|\n|\s)1\.\s+\S.*(?:^|\n|\s)2\.\s+\S",
    re.IGNORECASE | re.DOTALL,
)
_BULLET_FIELD_REGEX = re.compile(
    r"(?:^|\n)\s*[-*]\s*[^:\n]{2,80}:",
    re.IGNORECASE,
)
_INLINE_FIELD_REGEX = re.compile(
    r"\b(?:Load(?:\s*ID)?|Load/Pro|BOL|DO|PO|Invoice|Claim|Ticket|Case|Carrier|"
    r"Status|Response|Amount|Store|Division|Code|RA|RDO|Pro)\s*(?:/[^:]{1,24})?:",
    re.IGNORECASE,
)
_CASE_REPORTING_REGEX = re.compile(
    r"\b(the following has been reported|reported:|case details|scenario:|"
    r"carrier response|customer response|stakeholder response|status:)\b",
    re.IGNORECASE,
)
_QUOTED_OPERATIONAL_NOTE_REGEX = re.compile(
    r"\"[^\"]{12,}\"|\b(?:states?|reported|requested|confirmed|advises?|responded|says)\b",
    re.IGNORECASE,
)
_TASK_VERB_REGEX = re.compile(
    r"\b(?:confirm|compile|generate|calculate|update|list|draft|recommend|determine|"
    r"validate|identify|create|set up|build|prepare)\b",
    re.IGNORECASE,
)
_MONTH_VALUE = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?"
)
_CANDIDATE_VALUE_REGEX = re.compile(
    r"\$[\d,]+(?:\.\d{2})?"
    r"|\b\d+(?:\.\d+)?%"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:" + _MONTH_VALUE + r")\b"
    r"|\b(?:" + _MONTH_VALUE + r")\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{2,4})?\b"
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b(?:DO|PO|BOL|BL|RA|RDO|RPOD|POD|Claim|Invoice|Ticket|Case|Load|Pro)"
    r"\s*[:#-]?\s*[A-Za-z0-9-]{3,}\b"
    r"|\b[A-Z]{2,}[-#]?\d{2,}\b"
    r"|\b(?:open|closed|approved|denied|rejected|pending|filed|validated|paid|"
    r"unpaid|resolved|unresolved|delivered|returned|lost|short|overage|shortage)\b"
    r"|\b\d{3,}\b"
    r"|\"[^\"]{2,}\"",
    re.IGNORECASE,
)
_CORRECTION_OPENER_REGEX = re.compile(
    r"^\s*(no|nah|actually|correction|rather|instead)\b",
    re.IGNORECASE,
)
_CONTRASTIVE_CORRECTION_REGEX = re.compile(
    r"\b(?:not|instead of|rather than)\b.+\b(?:is|was|were|are|be|should be)\b",
    re.IGNORECASE,
)


def _call_ollama_generate(user_prompt: str, system_prompt: str, config: LLMConfig) -> str:
    if config.provider.lower() != "ollama":
        raise ValueError(f"Unsupported provider for context mode: {config.provider!r}")

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


def _validate_context_payload(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Context mode payload must be a JSON object")

    required_fields = {"mode", "confidence", "reasoning"}
    missing_fields = sorted(required_fields - set(payload))
    if missing_fields:
        raise KeyError(", ".join(missing_fields))

    mode = payload["mode"]
    confidence = payload["confidence"]
    reasoning = payload["reasoning"]

    if mode not in _ALLOWED_MODES:
        raise ValueError("Invalid mode")
    if confidence not in _ALLOWED_CONFIDENCE:
        raise ValueError("Invalid confidence")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("Invalid reasoning")

    return {
        "mode": mode,
        "confidence": confidence,
        "reasoning": reasoning.strip(),
    }


def _is_abbreviation(term: str) -> bool:
    return term == term.upper() and term.replace("-", "").isalnum()


def _tokenize(query: str, min_token_length: int = 3) -> list[str]:
    raw_tokens = re.split(r"[\s.,;:!?()\[\]{}'\"/\\]+", query.lower())
    return [token for token in raw_tokens if len(token) >= min_token_length]


def _find_domain_terms(query: str) -> list[str]:
    query_lower = query.lower()
    tokens = _tokenize(query)
    matched_terms: list[str] = []

    for term in STRONG_IN_TERMS:
        if _is_abbreviation(term):
            if re.search(rf"\b{re.escape(term)}\b", query, re.IGNORECASE):
                matched_terms.append(term)
        elif " " in term:
            if term.lower() in query_lower:
                matched_terms.append(term)
        elif term in tokens or term in query_lower:
            matched_terms.append(term)

    return matched_terms


def _summarize_prior_answer_for_context(answer_text: str | None) -> str:
    if not answer_text:
        return ""

    normalized = " ".join(answer_text.split())
    words = normalized.split()
    if len(words) <= 150:
        return normalized

    summary = " ".join(words[:150])
    if len(words) > 200:
        return f"{summary} [...]"
    return summary


def _starts_with_specific_term(query: str) -> bool:
    stripped = query.strip()
    lower = stripped.lower()

    if re.match(r"^[A-Z]{2,}(?:\s+\d+)?\b", stripped):
        return True

    for term in STRONG_IN_TERMS:
        term_lower = term.lower()
        if " " in term:
            if lower.startswith(term_lower):
                return True
            continue

        if _is_abbreviation(term):
            if re.match(rf"^{re.escape(term)}(?:\b|\s+\d+)", stripped, re.IGNORECASE):
                return True
            continue

        if lower.startswith(f"{term_lower} "):
            return True
        if lower == term_lower:
            return True

    return False


def _looks_like_complete_question(query: str) -> bool:
    stripped = query.strip()
    tokens = re.findall(r"[A-Za-z0-9']+", stripped)
    lowered_tokens = [token.lower() for token in tokens]

    if len(tokens) <= 5:
        return False

    starts_like_question = (
        stripped.endswith("?")
        or lowered_tokens[0] in {"what", "how", "why", "when", "where", "who", "which"}
    )
    has_verb = any(token in _VERB_HINTS for token in lowered_tokens)
    has_followup_pronoun = any(token in _FOLLOWUP_PRONOUNS for token in lowered_tokens)

    return starts_like_question and has_verb and not has_followup_pronoun


def has_case_study_signals(query: str) -> bool:
    stripped = query.strip()
    tokens = re.findall(r"[A-Za-z0-9']+", stripped)
    if len(tokens) < 18:
        return False

    score = 0

    has_document_anchor = bool(_DOCUMENT_ANCHOR_REGEX.search(stripped))
    has_numbered_tasks = bool(_NUMBERED_TASK_REGEX.search(stripped))
    field_count = len(_BULLET_FIELD_REGEX.findall(stripped))
    field_count += len(_INLINE_FIELD_REGEX.findall(stripped))

    if has_document_anchor:
        score += 2
    if has_numbered_tasks:
        score += 2
    if field_count >= 2:
        score += 2
    elif field_count == 1:
        score += 1
    if _CASE_REPORTING_REGEX.search(stripped):
        score += 1
    if _QUOTED_OPERATIONAL_NOTE_REGEX.search(stripped):
        score += 1
    if _TASK_VERB_REGEX.search(stripped):
        score += 1
    if len(tokens) > 50 and (has_document_anchor or has_numbered_tasks):
        score += 1

    return score >= 4


def _has_standalone_signals(query: str) -> bool:
    tokens = re.findall(r"[A-Za-z0-9']+", query)
    lowered_tokens = [token.lower() for token in tokens]
    has_followup_pronoun = any(token in _FOLLOWUP_PRONOUNS for token in lowered_tokens)

    if has_case_study_signals(query):
        return True
    if len(tokens) > 15 and not has_followup_pronoun:
        return True
    if len(tokens) > 15 and _find_domain_terms(query):
        return True
    if _starts_with_specific_term(query):
        return True
    if _looks_like_complete_question(query):
        return True
    return False


def _check_citation_intent(query: str, session: SessionContext) -> bool:
    citation_match = next((pattern for pattern in _CITATION_REGEXES if pattern.search(query)), None)
    if citation_match is None:
        return False

    if not session.last_citations:
        logger.debug(
            "[ContextMode] citation_lookup pattern matched but session.last_citations is empty; falling through"
        )
        return False

    logger.debug(
        "[ContextMode] citation_lookup detected via regex pattern=%s",
        citation_match.pattern,
    )
    return True


def is_correction_challenge(query: str) -> bool:
    """Return True when the user is challenging or correcting a prior answer.

    Keep this deliberately conservative: it only runs when a prior turn exists,
    and mostly keys off pronoun-based challenges or explicit candidate values.
    """
    stripped = query.strip()
    if not stripped:
        return False

    tokens = re.findall(r"[A-Za-z0-9']+", stripped)
    lowered_tokens = [token.lower() for token in tokens]
    has_pronoun = any(token in _FOLLOWUP_PRONOUNS for token in lowered_tokens)
    has_candidate_value = bool(_CANDIDATE_VALUE_REGEX.search(stripped))

    for pattern in _CORRECTION_REGEXES:
        if pattern.pattern == _CORRECTION_OPENER_REGEX.pattern:
            continue
        if not pattern.search(stripped):
            continue
        return True

    if _CORRECTION_OPENER_REGEX.search(stripped):
        opener = _CORRECTION_OPENER_REGEX.search(stripped).group(1).lower()
        if opener == "actually":
            return has_candidate_value
        if opener in {"rather", "instead"}:
            return has_candidate_value or has_pronoun
        return has_candidate_value or has_pronoun or len(tokens) <= 8

    if _CONTRASTIVE_CORRECTION_REGEX.search(stripped):
        return has_candidate_value or has_pronoun

    return False


def _build_context_mode_result(
    mode: str,
    mode_confidence: str,
    mode_method: str,
) -> ContextModeResult:
    if mode == "citation_lookup":
        return ContextModeResult(
            mode=mode,
            track="citation",
            requires_retrieval=False,
            requires_reformulation=False,
            prior_answer_needed=False,
            mode_confidence=mode_confidence,
            mode_method=mode_method,
            reformulated_query=None,
        )

    if mode == "answer_transform":
        return ContextModeResult(
            mode=mode,
            track="transform",
            requires_retrieval=False,
            requires_reformulation=False,
            prior_answer_needed=True,
            mode_confidence=mode_confidence,
            mode_method=mode_method,
            reformulated_query=None,
        )

    return ContextModeResult(
        mode=mode,
        track="retrieval",
        requires_retrieval=True,
        requires_reformulation=(mode == "retrieval_followup"),
        prior_answer_needed=False,
        mode_confidence=mode_confidence,
        mode_method=mode_method,
        reformulated_query=None,
    )


def _classify_by_patterns(query: str, session: SessionContext) -> tuple[str, str] | None:
    if not session.turns:
        logger.debug("[ContextMode] No prior turns; using standalone mode")
        return "standalone", "high"

    if _check_citation_intent(query, session):
        return "citation_lookup", "high"

    transform_match = next((pattern for pattern in _TRANSFORM_REGEXES if pattern.search(query)), None)
    if transform_match is None and _TRANSFORM_PREFIX_REGEX.search(query):
        transform_match = _TRANSFORM_PREFIX_REGEX
    followup_match = next((pattern for pattern in _FOLLOWUP_REGEXES if pattern.search(query)), None)
    matched_domain_terms = _find_domain_terms(query)
    case_study_signals = has_case_study_signals(query)
    standalone_signals = _has_standalone_signals(query)

    logger.debug(
        "[ContextMode] Regex analysis transform=%s followup=%s domain_terms=%s case_study=%s standalone=%s",
        transform_match.pattern if transform_match else None,
        followup_match.pattern if followup_match else None,
        matched_domain_terms,
        case_study_signals,
        standalone_signals,
    )

    if transform_match and not matched_domain_terms:
        return "answer_transform", "high"
    if transform_match and matched_domain_terms:
        return "retrieval_followup", "high"
    if is_correction_challenge(query):
        return "retrieval_followup", "high"
    if standalone_signals:
        return "standalone", "high"
    if followup_match:
        return "retrieval_followup", "high"
    return None


def run_stage2(
    query: str,
    query_understanding: QueryUnderstandingResult,
    session: SessionContext,
    config: LLMConfig,
) -> ContextModeResult:
    """Classify whether the current message is new, follow-up retrieval, or transform."""
    _ = query_understanding

    regex_result = _classify_by_patterns(query, session)
    if regex_result is not None:
        mode, confidence = regex_result
        return _build_context_mode_result(mode, confidence, "regex")

    prior_answer_summary = _summarize_prior_answer_for_context(session.last_answer)

    try:
        raw_output = _call_ollama_generate(
            user_prompt=CONTEXT_MODE_USER_TEMPLATE.format(
                prior_answer_summary=prior_answer_summary,
                current_query=query,
            ),
            system_prompt=CONTEXT_SYSTEM_PROMPT,
            config=config,
        )
        logger.debug("[ContextMode] Raw model output: %s", raw_output)

        parsed_payload = json.loads(_strip_json_fences(raw_output))
        validated_payload = _validate_context_payload(parsed_payload)

        logger.debug(
            "[ContextMode] Model decision mode=%s confidence=%s reasoning=%s",
            validated_payload["mode"],
            validated_payload["confidence"],
            validated_payload["reasoning"],
        )
        if validated_payload["mode"] == "citation_lookup" and not session.last_citations:
            logger.debug(
                "[ContextMode] Model returned citation_lookup without prior citations; using standalone fallback"
            )
            return _build_context_mode_result("standalone", "low", "fallback_standalone")

        if validated_payload["mode"] == "answer_transform" and not session.last_answer:
            logger.debug(
                "[ContextMode] Model returned answer_transform without prior answer; using standalone fallback"
            )
            return _build_context_mode_result("standalone", "low", "fallback_standalone")

        return _build_context_mode_result(
            validated_payload["mode"],
            validated_payload["confidence"],
            "llm",
        )
    except Exception as exc:
        logger.warning(
            "[ContextMode] Falling back to %s after model failure: %s",
            config.fallback_behavior,
            exc,
        )
        return _build_context_mode_result("standalone", "low", "fallback_standalone")
