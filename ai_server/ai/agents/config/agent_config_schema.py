from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    provider: str
    model_name: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    fallback_behavior: str


@dataclass
class DomainGateConfig:
    strong_in_domain_threshold: float
    strong_out_domain_threshold: float
    min_token_length: int


@dataclass
class ConfidenceGateConfig:
    default_threshold: float
    thresholds_by_style: dict[str, float] = field(default_factory=dict)

    def threshold_for_style(self, style: str) -> float:
        """Return the threshold for a given style, falling back to default."""
        return self.thresholds_by_style.get(style, self.default_threshold)


@dataclass
class PromptAssemblyConfig:
    vocabulary_block_enabled: bool
    max_chunks_in_prompt: int
    source_header_template: str
    default_style: str
    # Per-style chunk cap. When set, takes priority over max_chunks_in_prompt
    # for the matched style. Allows exploratory/comparative queries to receive
    # more context than direct/procedural ones.
    max_chunks_by_style: dict[str, int] = field(default_factory=dict)


@dataclass
class AnswerGeneratorConfig:
    model_name: str
    ollama_base_url: str
    timeout_seconds: int
    temperature: float
    max_tokens: int
    no_think_enabled: bool
    no_think_model_prefixes: list[str] = field(default_factory=list)


@dataclass
class CitationBuilderConfig:
    staleness_threshold_days: int
    max_citations_in_response: int


@dataclass
class FaithfulnessCheckConfig:
    penalty_low: float
    penalty_high: float
    enabled: bool


@dataclass
class SessionStoreConfig:
    ttl_seconds: int
    max_turns_in_window: int
    key_prefix: str
    enabled: bool


@dataclass
class AgentsConfig:
    domain_gate: DomainGateConfig
    query_understanding: LLMConfig
    context_mode: LLMConfig
    reformulator: LLMConfig
    retrieval_planner: LLMConfig
    confidence_gate: ConfidenceGateConfig
    prompt_assembly: PromptAssemblyConfig
    answer_generator: AnswerGeneratorConfig
    citation_builder: CitationBuilderConfig
    faithfulness_check: FaithfulnessCheckConfig
    session_store: "SessionStoreConfig" = field(
        default_factory=lambda: SessionStoreConfig(
            ttl_seconds=3600,
            max_turns_in_window=4,
            key_prefix="session:v1:",
            enabled=True,
        )
    )
