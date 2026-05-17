#!/usr/bin/env python3
"""Unit tests for Step 4 answer generation endpoint selection."""
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

import ai.pipeline.step4_answer_generator as step4_module
from ai.agents.config.agent_config_schema import AnswerGeneratorConfig
from ai.config.company_profile import QAConfig
from ai.pipeline.step3_prompt_assembler import PromptAssemblerResult


@contextmanager
def _patched_attr(obj, attr_name: str, replacement):
    original = getattr(obj, attr_name)
    setattr(obj, attr_name, replacement)
    try:
        yield
    finally:
        setattr(obj, attr_name, original)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _prompt_result() -> PromptAssemblerResult:
    return PromptAssemblerResult(
        assembled_prompt="QUESTION: What is a freight claim?\n\nANSWER:",
        system_prompt="Answer directly.",
        chunk_count_used=1,
        format_instruction="Respond briefly.",
        format_type="prose",
        style_used="direct",
        was_skipped=False,
        skip_reason=None,
        confidence_result=None,
    )


def _config(model_name: str, *, no_think_enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        answer_generator=AnswerGeneratorConfig(
            model_name=model_name,
            ollama_base_url="http://localhost:11434",
            timeout_seconds=30,
            temperature=0.1,
            max_tokens=80,
            no_think_enabled=no_think_enabled,
            no_think_model_prefixes=["qwen3", "qwen3.5"],
        )
    )


def _fake_profile():
    return SimpleNamespace(qa=QAConfig(suggested_prompts=[], no_result_message="No answer."))


def test_qwen_no_think_uses_native_chat_without_prompt_prefix() -> None:
    calls: dict[str, dict] = {}

    def fake_load_config():
        return _config("qwen3:32b", no_think_enabled=True)

    def fake_native(**kwargs):
        calls["native"] = kwargs
        return _FakeResponse(
            {
                "message": {
                    "role": "assistant",
                    "content": "A freight claim requests compensation for shipping loss or damage.",
                }
            }
        )

    def fake_openai(**kwargs):
        raise AssertionError("OpenAI-compatible endpoint should not be used for qwen3 no-think")

    with _patched_attr(step4_module, "load_agents_config", fake_load_config):
        with _patched_attr(step4_module, "load_company_profile", _fake_profile):
            with _patched_attr(step4_module, "_post_ollama_native_chat", fake_native):
                with _patched_attr(step4_module, "_post_ollama_openai_chat", fake_openai):
                    result = step4_module.run_answer_generator(_prompt_result())

    assert result.was_generated is True
    assert result.answer_text.startswith("A freight claim")
    assert result.no_think_injected is True
    assert "native" in calls
    assert calls["native"]["user_prompt"].startswith("QUESTION:")
    assert "/no_think" not in calls["native"]["user_prompt"]


def test_non_qwen_uses_openai_compatible_chat() -> None:
    calls: dict[str, dict] = {}

    def fake_load_config():
        return _config("llama3.1:8b", no_think_enabled=True)

    def fake_native(**kwargs):
        raise AssertionError("Native no-think endpoint should not be used for non-qwen model")

    def fake_openai(**kwargs):
        calls["openai"] = kwargs
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "A freight claim requests compensation.",
                        }
                    }
                ]
            }
        )

    with _patched_attr(step4_module, "load_agents_config", fake_load_config):
        with _patched_attr(step4_module, "load_company_profile", _fake_profile):
            with _patched_attr(step4_module, "_post_ollama_native_chat", fake_native):
                with _patched_attr(step4_module, "_post_ollama_openai_chat", fake_openai):
                    result = step4_module.run_answer_generator(_prompt_result())

    assert result.was_generated is True
    assert result.answer_text == "A freight claim requests compensation."
    assert result.no_think_injected is False
    assert "openai" in calls


def test_openai_reasoning_only_response_is_rejected_as_empty() -> None:
    def fake_load_config():
        return _config("llama3.1:8b", no_think_enabled=False)

    def fake_openai(**kwargs):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning": "Internal reasoning without final content.",
                        }
                    }
                ]
            }
        )

    with _patched_attr(step4_module, "load_agents_config", fake_load_config):
        with _patched_attr(step4_module, "load_company_profile", _fake_profile):
            with _patched_attr(step4_module, "_post_ollama_openai_chat", fake_openai):
                result = step4_module.run_answer_generator(_prompt_result())

    assert result.was_generated is False
    assert result.skip_reason == "empty_response"
    assert result.answer_text == "No answer."


if __name__ == "__main__":
    tests = [
        test_qwen_no_think_uses_native_chat_without_prompt_prefix,
        test_non_qwen_uses_openai_compatible_chat,
        test_openai_reasoning_only_response_is_rejected_as_empty,
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
