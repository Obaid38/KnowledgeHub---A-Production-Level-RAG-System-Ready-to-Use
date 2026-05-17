from dataclasses import dataclass, field


@dataclass
class PlannerTask:
    id: str
    task_text: str
    evidence_needed: list[str] = field(default_factory=list)


@dataclass
class PlannerRetrievalQuery:
    id: str
    task_ids: list[str] = field(default_factory=list)
    query: str = ""
    priority: str = "medium"


@dataclass
class RetrievalPlanResult:
    case_context_present: bool
    case_facts: list[str] = field(default_factory=list)
    tasks: list[PlannerTask] = field(default_factory=list)
    retrieval_queries: list[PlannerRetrievalQuery] = field(default_factory=list)
    preserve_for_answer: list[str] = field(default_factory=list)
    do_not_retrieve: list[str] = field(default_factory=list)
    answer_constraints: list[str] = field(default_factory=list)
    planner_method: str = "unknown"
    raw_output: str | None = None

