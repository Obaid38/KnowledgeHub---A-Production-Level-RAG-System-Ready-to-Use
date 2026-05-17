from dataclasses import dataclass


@dataclass
class QueryUnderstandingResult:
    in_domain: bool
    domain_confidence: str    # 'high' | 'medium' | 'low'
    refusal_reason: str | None
    style: str
    format_type: str
    format_is_explicit: bool
    length_hint: str
    classifier_method: str
