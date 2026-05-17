from dataclasses import dataclass


@dataclass
class ContextModeResult:
    # Valid modes: standalone, retrieval_followup, answer_transform, citation_lookup.
    mode: str
    track: str
    requires_retrieval: bool
    requires_reformulation: bool
    prior_answer_needed: bool
    mode_confidence: str
    mode_method: str
    reformulated_query: str | None
