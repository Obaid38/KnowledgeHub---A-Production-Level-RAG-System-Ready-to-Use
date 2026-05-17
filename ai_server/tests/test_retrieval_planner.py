#!/usr/bin/env python3
"""Unit tests for Stage 2b retrieval planning and multi-query retrieval wiring."""
import sys
from pathlib import Path
from types import SimpleNamespace

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

import ai.agents.stage2b_retrieval_planner as planner_module
import ai.pipeline.step1_retrieval_gate as retrieval_gate_module
from ai.agents.config.agent_config_schema import LLMConfig
from ai.agents.models.context_mode import ContextModeResult
from ai.agents.models.domain_signal import DomainSignal
from ai.agents.models.query_understanding import QueryUnderstandingResult
from ai.agents.models.retrieval_plan import (
    PlannerRetrievalQuery,
    PlannerTask,
    RetrievalPlanResult,
)
from ai.agents.models.session import SessionContext
from ai.agents.orchestrator import Group1Result


def _config() -> LLMConfig:
    return LLMConfig(
        provider="ollama",
        model_name="unused",
        temperature=0.0,
        max_tokens=900,
        timeout_seconds=1,
        fallback_behavior="passthrough_single_query",
    )


def _patch_attr(obj, attr_name: str, replacement):
    class _Patch:
        def __enter__(self):
            self.original = getattr(obj, attr_name)
            setattr(obj, attr_name, replacement)

        def __exit__(self, exc_type, exc, tb):
            setattr(obj, attr_name, self.original)

    return _Patch()


def _case_study_json(*args, **kwargs) -> str:
    return """{
  "case_context_present": true,
  "case_facts": [
    "Load ID / BOL: 17847773",
    "Carrier: CH Robinson",
    "The entire trailer was stolen"
  ],
  "tasks": [
    {
      "id": "task_1",
      "task_text": "List all required notifications",
      "evidence_needed": ["SOP-02 theft incident notification recipients and stakeholders"]
    },
    {
      "id": "task_2",
      "task_text": "Set up tracking milestones",
      "evidence_needed": ["SOP-02 theft incident timeline and 24-hour claim submission"]
    }
  ],
  "retrieval_queries": [
    {
      "id": "q1",
      "task_ids": ["task_1"],
      "query": "SOP-02 theft incident required notifications Logistics Security SEACLAIMS carrier internal stakeholders",
      "priority": "high"
    },
    {
      "id": "q2",
      "task_ids": ["task_2"],
      "query": "SOP-02 theft incident timeline immediate notification 24-hour claim submission",
      "priority": "high"
    }
  ],
  "preserve_for_answer": [
    "Load ID / BOL: 17847773",
    "Carrier: CH Robinson"
  ],
  "do_not_retrieve": ["17847773"],
  "answer_constraints": [
    "Use case facts as user-provided inputs, not source evidence"
  ]
}"""


def _simple_json(*args, **kwargs) -> str:
    return """{
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
    "Answer only from retrieved escalation evidence"
  ]
}"""


def test_retrieval_planner_case_study_preserves_ids_without_retrieving_them() -> None:
    with _patch_attr(planner_module, "_call_ollama_generate", _case_study_json):
        result = planner_module.run_stage2b("case prompt", _config())

    assert result.planner_method == "llm"
    assert result.case_context_present is True
    assert "Load ID / BOL: 17847773" in result.case_facts
    assert "17847773" in result.do_not_retrieve
    assert len(result.tasks) == 2
    assert len(result.retrieval_queries) == 2
    assert all("17847773" not in q.query for q in result.retrieval_queries)


def test_retrieval_planner_simple_prompt_uses_one_query() -> None:
    with _patch_attr(planner_module, "_call_ollama_generate", _simple_json):
        result = planner_module.run_stage2b("What are escalation levels?", _config())

    assert result.case_context_present is False
    assert result.case_facts == []
    assert len(result.tasks) == 1
    assert len(result.retrieval_queries) == 1
    assert "escalation matrix SOP" in result.retrieval_queries[0].query


def test_retrieval_planner_invalid_json_falls_back_to_single_query() -> None:
    def bad_json(*args, **kwargs) -> str:
        return "not json"

    with _patch_attr(planner_module, "_call_ollama_generate", bad_json):
        result = planner_module.run_stage2b("What is POD?", _config())

    assert result.planner_method == "fallback_passthrough"
    assert len(result.retrieval_queries) == 1
    assert result.retrieval_queries[0].query == "What is POD?"


def _group1_with_plan(plan: RetrievalPlanResult) -> Group1Result:
    query = "planned query"
    return Group1Result(
        query_original=query,
        query_for_retrieval=query,
        domain_signal=DomainSignal(
            domain_signal="clear_in",
            format_hint=None,
            format_is_explicit=False,
            matched_terms=["claim"],
            match_density=0.2,
            gate_decision="fast_accept",
        ),
        understanding=QueryUnderstandingResult(
            in_domain=True,
            domain_confidence="high",
            refusal_reason=None,
            style="procedural",
            format_type="numbered_list",
            format_is_explicit=False,
            length_hint="infer",
            classifier_method="test",
        ),
        context_mode=ContextModeResult(
            mode="standalone",
            track="retrieval",
            requires_retrieval=True,
            requires_reformulation=False,
            prior_answer_needed=False,
            mode_confidence="high",
            mode_method="test",
            reformulated_query=None,
        ),
        should_retrieve=True,
        should_refuse=False,
        refusal_message=None,
        style="procedural",
        format_type="numbered_list",
        length_hint="infer",
        total_latency_ms=0.0,
        retrieval_plan=plan,
    )


def test_retrieval_gate_runs_each_subquery_and_dedupes_chunks() -> None:
    plan = RetrievalPlanResult(
        case_context_present=False,
        tasks=[PlannerTask(id="task_1", task_text="Find evidence")],
        retrieval_queries=[
            PlannerRetrievalQuery(id="q1", task_ids=["task_1"], query="first query", priority="high"),
            PlannerRetrievalQuery(id="q2", task_ids=["task_1"], query="second query", priority="high"),
        ],
        planner_method="llm",
    )

    chunk_a_low = SimpleNamespace(chunk_id="chunk-a", score=0.55, rerank_score=0.55)
    chunk_a_high = SimpleNamespace(chunk_id="chunk-a", score=0.91, rerank_score=0.91)
    chunk_b = SimpleNamespace(chunk_id="chunk-b", score=0.72, rerank_score=0.72)
    calls: list[str] = []

    def fake_search(*, query_text: str, category_filter):
        calls.append(query_text)
        if query_text == "first query":
            return [chunk_a_low, chunk_b]
        return [chunk_a_high]

    with (
        _patch_attr(retrieval_gate_module, "run_group1", lambda query, session: _group1_with_plan(plan)),
        _patch_attr(retrieval_gate_module, "_search_for_query", fake_search),
    ):
        result = retrieval_gate_module.run_retrieval_gate(
            "planned query",
            SessionContext(session_id="test"),
        )

    assert calls == ["first query", "second query"]
    assert result.planner_used is True
    assert result.chunk_count == 2
    assert result.chunks[0].chunk_id == "chunk-a"
    assert result.top_score == 0.91
    assert result.subquery_matches["chunk-a"] == ["q1", "q2"]


def test_search_for_query_caps_chunks_when_reranker_disabled() -> None:
    chunks = [
        SimpleNamespace(chunk_id=f"chunk-{index}", score=1.0 - (index * 0.01), rerank_score=None)
        for index in range(5)
    ]

    def fake_search_collection(**kwargs):
        return chunks, 0

    with (
        _patch_attr(retrieval_gate_module, "RERANKER_ENABLED", False),
        _patch_attr(retrieval_gate_module, "RETRIEVAL_TOP_K_POST_RERANK", 3),
        _patch_attr(retrieval_gate_module, "embed_query", lambda query: [0.1, 0.2]),
        _patch_attr(retrieval_gate_module, "bm25_embed_query", lambda query: object()),
        _patch_attr(retrieval_gate_module, "search_collection", fake_search_collection),
    ):
        result = retrieval_gate_module._search_for_query(
            query_text="planned query",
            category_filter=None,
        )

    assert len(result) == 3
    assert [chunk.chunk_id for chunk in result] == ["chunk-0", "chunk-1", "chunk-2"]


if __name__ == "__main__":
    tests = [
        test_retrieval_planner_case_study_preserves_ids_without_retrieving_them,
        test_retrieval_planner_simple_prompt_uses_one_query,
        test_retrieval_planner_invalid_json_falls_back_to_single_query,
        test_retrieval_gate_runs_each_subquery_and_dedupes_chunks,
        test_search_for_query_caps_chunks_when_reranker_disabled,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  PASS  {test_fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test_fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
