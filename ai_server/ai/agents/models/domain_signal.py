from dataclasses import dataclass


@dataclass
class DomainSignal:
    domain_signal: str        # 'clear_in' | 'clear_out' | 'borderline' | 'unknown'
    format_hint: str | None   # 'steps' | 'bullets' | 'table' | 'short' | 'long' | None
    format_is_explicit: bool
    matched_terms: list[str]  # terms matched from STRONG_IN_TERMS — for debugging
    match_density: float      # strong_in_matches / max(total_tokens, 1)
    gate_decision: str        # 'fast_accept' | 'fast_reject' | 'escalate_to_llm'
