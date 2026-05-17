"""Stage 0: deterministic vocabulary gate.

No LLM is called. Classifies a query using vocabulary matching and regex patterns,
returning a DomainSignal with a gate_decision of "fast_accept", "fast_reject", or
"escalate_to_llm".

The gate is advisory. Stage 1 may still override the outcome.
"""
import logging
import re

from ai.agents.config.agent_config_schema import DomainGateConfig
from ai.agents.models.domain_signal import DomainSignal
from ai.config.company_profile import load_company_profile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

_PROFILE = load_company_profile()


def _abbreviation_terms(items: list[str]) -> list[str]:
    terms: list[str] = []
    for item in items:
        if ":" in item:
            candidate = item.split(":", 1)[0].strip()
            if candidate:
                terms.append(candidate)
    return terms


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
    return result

# High-signal terms are strong enough to support deterministic fast-accept.
HIGH_SIGNAL_IN_TERMS: list[str] = _dedupe_preserve_order(
    list(_PROFILE.domain.strong_in_terms)
    + list(_PROFILE.company.aliases)
    + list(_PROFILE.domain.teams)
    + list(_PROFILE.domain.systems)
    + list(_PROFILE.domain.customers)
    + list(_PROFILE.domain.carriers)
    + list(_PROFILE.domain.warehouse_partners)
    + _abbreviation_terms(_PROFILE.domain.abbreviations)
)

# Generic domain words signal possible relevance but are too broad to fast-accept
# on a single match.
GENERIC_DOMAIN_TERMS: list[str] = list(_PROFILE.domain.generic_domain_terms)

# Combined view used by other stages that only need a broad domain-term list.
STRONG_IN_TERMS: list[str] = HIGH_SIGNAL_IN_TERMS + GENERIC_DOMAIN_TERMS

# Weak in-domain terms contribute contextual signal only for human reasoning and docs.
WEAK_IN_TERMS: list[str] = [
    "document", "process", "workflow", "role", "responsibility",
    "timeline", "deadline", "sla",
]

# Compiled strong-out patterns. Fast reject only fires when domain evidence count is 0.
_STRONG_OUT_PATTERNS: list[re.Pattern] = [
    # General knowledge / trivia
    re.compile(
        r"\b(what is the capital( of)?|who invented|what year was"
        r"|when did .+ die|explain .+ theory|history of .+ war)\b",
        re.IGNORECASE,
    ),
    # Government / politics / public office
    re.compile(
        r"\b(president of|prime minister of|vice president of|governor of|mayor of)\b",
        re.IGNORECASE,
    ),
    # Entertainment and lifestyle
    re.compile(
        r"\b(movie|song|recipe|celebrity|tv show|weather forecast|horoscope)\b",
        re.IGNORECASE,
    ),
    # Personal / creative requests
    re.compile(
        r"\b(my salary|my personal|my relationship|joke|meme|poem"
        r"|write me a (story|poem|song|essay)|tell me a (story|joke))\b",
        re.IGNORECASE,
    ),
    # Academic / science domains
    re.compile(
        r"\b(solve this equation|calculate \d|physics|chemistry|biology"
        r"|mathematics|algebra|geometry|periodic table)\b",
        re.IGNORECASE,
    ),
    # Sports results and general sporting events
    re.compile(
        r"\b(who won|who beat|who lost|final score|match result|box score"
        r"|world cup|super bowl|world series|stanley cup|nba finals"
        r"|nfl draft|premier league|champions league|olympic medal)\b",
        re.IGNORECASE,
    ),
]

# Format cue patterns - ordered; first match wins.
_FORMAT_PATTERNS: dict[str, re.Pattern] = {
    "steps": re.compile(
        r"\b(step by step|steps to|how do i|procedure for|walk me through|what are the steps)\b",
        re.IGNORECASE,
    ),
    "bullets": re.compile(
        r"\b(list|bullet|summarize|summary|key points|overview)\b",
        re.IGNORECASE,
    ),
    "table": re.compile(
        r"\b(in a table|as a table|tabular|compare.*table)\b",
        re.IGNORECASE,
    ),
    "short": re.compile(
        r"\b(briefly|brief|quick|short answer|in one sentence|tldr|tl;dr)\b",
        re.IGNORECASE,
    ),
    "long": re.compile(
        r"\b(in detail|detailed|comprehensive|full explanation|explain everything)\b",
        re.IGNORECASE,
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_abbreviation(term: str) -> bool:
    """Return True if term should be matched with word boundaries."""
    return term == term.upper() and term.replace("-", "").isalnum()


def _tokenize(query: str, min_token_length: int) -> list[str]:
    """Split query into lowercase tokens, filtering short ones."""
    raw = re.split(r"[\s.,;:!?()\[\]{}'\"\/\\]+", query.lower())
    return [token for token in raw if len(token) >= min_token_length]


def _match_terms(query: str, tokens: list[str], terms: list[str]) -> list[str]:
    """Return matched terms using strict matching rules by term type."""
    query_lower = query.lower()
    matched: list[str] = []

    for term in terms:
        if _is_abbreviation(term):
            if re.search(rf"\b{re.escape(term)}\b", query, re.IGNORECASE):
                matched.append(term)
        elif " " in term:
            if term.lower() in query_lower:
                matched.append(term)
        elif term in tokens:
            matched.append(term)

    return matched


def _count_strong_out(query: str) -> int:
    """Count how many strong-out patterns match the query."""
    return sum(1 for pattern in _STRONG_OUT_PATTERNS if pattern.search(query))


def _detect_format_hint(query: str) -> tuple[str | None, bool]:
    """Return (format_hint, format_is_explicit). First matching pattern wins."""
    for fmt_name, pattern in _FORMAT_PATTERNS.items():
        if pattern.search(query):
            return fmt_name, True
    return None, False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_stage0(query: str, config: DomainGateConfig) -> DomainSignal:
    """Run the deterministic domain gate against a query."""
    tokens = _tokenize(query, config.min_token_length)
    total_tokens = max(len(tokens), 1)

    high_signal_matches = _match_terms(query, tokens, HIGH_SIGNAL_IN_TERMS)
    generic_matches = _match_terms(query, tokens, GENERIC_DOMAIN_TERMS)
    high_signal_count = len(high_signal_matches)
    generic_count = len(generic_matches)
    matched_terms = high_signal_matches + generic_matches
    domain_evidence_count = high_signal_count + generic_count
    strong_out_count = _count_strong_out(query)
    match_density = domain_evidence_count / total_tokens

    format_hint, format_is_explicit = _detect_format_hint(query)

    logger.debug(
        "[Stage0] query=%r tokens=%d high_signal=%d generic=%d strong_out=%d density=%.3f matched=%s",
        query[:80],
        total_tokens,
        high_signal_count,
        generic_count,
        strong_out_count,
        match_density,
        matched_terms,
    )

    if strong_out_count > 0 and domain_evidence_count == 0:
        domain_signal = "clear_out"
        gate_decision = "fast_reject"
    elif high_signal_count > 0:
        domain_signal = "clear_in"
        gate_decision = "fast_accept"
    elif generic_count >= 2 and match_density >= config.strong_in_domain_threshold:
        domain_signal = "clear_in"
        gate_decision = "fast_accept"
    elif domain_evidence_count > 0:
        domain_signal = "borderline"
        gate_decision = "escalate_to_llm"
    else:
        domain_signal = "unknown"
        gate_decision = "escalate_to_llm"

    logger.info(
        "[Stage0] decision=%s gate=%s density=%.3f matched=%s",
        domain_signal,
        gate_decision,
        match_density,
        matched_terms,
    )

    return DomainSignal(
        domain_signal=domain_signal,
        format_hint=format_hint,
        format_is_explicit=format_is_explicit,
        matched_terms=matched_terms,
        match_density=match_density,
        gate_decision=gate_decision,
    )
