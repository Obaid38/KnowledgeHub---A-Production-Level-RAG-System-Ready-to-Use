"""Step 4 — Answer Generator.

Sends the assembled prompt from Step 3 to an Ollama LLM. Qwen-style no-think
generation uses Ollama native /api/chat with think=false; other models use
/v1/chat/completions.
and returns a structured result. Never raises — all errors are captured
in the returned result object.
"""
import logging
import re
import time
from dataclasses import dataclass

import httpx

from ai.agents.config.agent_config_loader import load_agents_config
from ai.config.company_profile import load_company_profile
from ai.pipeline.step3_prompt_assembler import PromptAssemblerResult

logger = logging.getLogger("knowledge_hub.pipeline.step4")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AnswerGeneratorResult:
    answer_text: str
    was_generated: bool
    skip_reason: str | None
    model_used: str
    latency_ms: float
    prompt_token_estimate: int          # len(prompt) // 4
    no_think_injected: bool
    prompt_result: PromptAssemblerResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_inject_no_think(model_name: str, prefixes: list[str]) -> bool:
    """Return True if model_name starts with any of the given prefixes."""
    lower = model_name.lower()
    return any(lower.startswith(p.lower()) for p in prefixes)


def _uses_native_no_think_chat(model_name: str, prefixes: list[str], no_think_enabled: bool) -> bool:
    """Return True when Ollama native chat should be used to disable thinking."""
    return no_think_enabled and _should_inject_no_think(model_name, prefixes)


def _post_ollama_native_chat(
    *,
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> httpx.Response:
    """Call Ollama /api/chat with think=false for Qwen-style reasoning models."""
    return httpx.post(
        f"{base_url}/api/chat",
        json={
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "think": False,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        },
        timeout=float(timeout_seconds),
    )


def _post_ollama_openai_chat(
    *,
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> httpx.Response:
    """Call Ollama's OpenAI-compatible chat endpoint for non-thinking models."""
    return httpx.post(
        f"{base_url}/v1/chat/completions",
        json={
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=float(timeout_seconds),
    )


def _parse_native_chat_response(data: object) -> str:
    """Extract assistant content from Ollama /api/chat response payload."""
    if not isinstance(data, dict):
        raise ValueError("Native chat response must be a JSON object")

    message = data.get("message")
    answer_text = message.get("content", "").strip() if isinstance(message, dict) else ""
    if not answer_text:
        raise ValueError("Native chat response contained no message content")
    return answer_text


def _parse_openai_chat_response(data: object) -> str:
    """Extract assistant content from Ollama /v1/chat/completions response payload."""
    if not isinstance(data, dict):
        raise ValueError("OpenAI-compatible chat response must be a JSON object")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI-compatible chat response contained no choices")

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    answer_text = message.get("content", "").strip() if isinstance(message, dict) else ""
    if not answer_text:
        reasoning = message.get("reasoning", "") if isinstance(message, dict) else ""
        if reasoning:
            raise ValueError("OpenAI-compatible chat response contained reasoning but no content")
        raise ValueError("OpenAI-compatible chat response contained no message content")
    return answer_text


def _ensure_bullet_readability(answer_text: str, format_type: str) -> str:
    """Fallback: if bullets were requested but LLM returned prose, convert paragraphs to bullets.

    Only fires when format_type is 'bullets' and the response contains no markdown
    bullet or numbered-list markers. The Sources: section is always preserved verbatim.
    """
    if format_type != "bullets":
        return answer_text

    # Already has bullets — leave it alone
    if re.search(r"^\s*[-*•]|^\d+\.\s", answer_text, re.MULTILINE):
        return answer_text

    # Split off the Sources: section (preserve it exactly)
    sources_split = re.split(r"(\n\s*Sources:\s*\n)", answer_text, maxsplit=1, flags=re.IGNORECASE)
    body = sources_split[0]
    tail = "".join(sources_split[1:])

    # Convert paragraphs to bullets
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
    bulleted = "\n".join(f"- {p}" for p in paragraphs)

    logger.info("[Step4] bullet_readability_fallback fired: LLM returned prose for bullets request; converted %d paragraph(s)", len(paragraphs))
    return bulleted + ("\n" + tail.strip() if tail.strip() else "")


def _skipped_result(
    prompt_result: PromptAssemblerResult,
    skip_reason: str,
    no_result_message: str,
    model_name: str,
    latency_ms: float,
) -> AnswerGeneratorResult:
    return AnswerGeneratorResult(
        answer_text=no_result_message,
        was_generated=False,
        skip_reason=skip_reason,
        model_used=model_name,
        latency_ms=latency_ms,
        prompt_token_estimate=0,
        no_think_injected=False,
        prompt_result=prompt_result,
    )


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def run_answer_generator(prompt_result: PromptAssemblerResult) -> AnswerGeneratorResult:
    """Send the assembled prompt to Ollama and return the generated answer.

    Skips generation if the prompt was not assembled (low confidence, refused, etc.).
    Never raises — all errors are caught and returned as result objects.
    """
    start = time.perf_counter()

    # --- Load config ---
    try:
        cfg = load_agents_config()
        ag = cfg.answer_generator
        no_result_message = load_company_profile().qa.no_result_message
    except Exception as exc:
        logger.error("[Step4] Failed to load config: %s", exc)
        elapsed = (time.perf_counter() - start) * 1000
        return _skipped_result(prompt_result, "config_error", "Configuration error.", "", elapsed)

    model_name = ag.model_name

    # --- Guard: skip if prompt was not assembled ---
    if prompt_result.was_skipped:
        logger.info(
            "[Step4] Skipping generation: prompt was skipped (reason=%s)",
            prompt_result.skip_reason,
        )
        elapsed = (time.perf_counter() - start) * 1000
        return _skipped_result(prompt_result, prompt_result.skip_reason, no_result_message, model_name, elapsed)

    # --- Prepare the prompt ---
    final_prompt = prompt_result.assembled_prompt
    no_think = _uses_native_no_think_chat(
        model_name,
        ag.no_think_model_prefixes,
        ag.no_think_enabled,
    )

    prompt_token_estimate = max(1, len(final_prompt) // 4)
    endpoint_name = "/api/chat think=false" if no_think else "/v1/chat/completions"

    # --- Call Ollama ---
    try:
        logger.info(
            "[Step4] Calling Ollama: model=%s endpoint=%s prompt_tokens~%d timeout=%ds",
            model_name,
            endpoint_name,
            prompt_token_estimate,
            ag.timeout_seconds,
        )

        if no_think:
            response = _post_ollama_native_chat(
                base_url=ag.ollama_base_url,
                model_name=model_name,
                system_prompt=prompt_result.system_prompt,
                user_prompt=final_prompt,
                temperature=ag.temperature,
                max_tokens=ag.max_tokens,
                timeout_seconds=ag.timeout_seconds,
            )
        else:
            response = _post_ollama_openai_chat(
                base_url=ag.ollama_base_url,
                model_name=model_name,
                system_prompt=prompt_result.system_prompt,
                user_prompt=final_prompt,
                temperature=ag.temperature,
                max_tokens=ag.max_tokens,
                timeout_seconds=ag.timeout_seconds,
            )
        response.raise_for_status()

    except httpx.TimeoutException:
        logger.error("[Step4] Ollama timeout after %ds — model=%s", ag.timeout_seconds, model_name)
        elapsed = (time.perf_counter() - start) * 1000
        return _skipped_result(prompt_result, "ollama_timeout", no_result_message, model_name, elapsed)

    except httpx.ConnectError:
        logger.error("[Step4] Cannot connect to Ollama at %s — is it running?", ag.ollama_base_url)
        elapsed = (time.perf_counter() - start) * 1000
        return _skipped_result(prompt_result, "ollama_connection_error", no_result_message, model_name, elapsed)

    except Exception as exc:
        logger.error("[Step4] Ollama call failed: %s", exc)
        elapsed = (time.perf_counter() - start) * 1000
        return _skipped_result(prompt_result, "generation_error", no_result_message, model_name, elapsed)

    # --- Parse response ---
    try:
        data = response.json()
        if no_think:
            answer_text = _parse_native_chat_response(data)
        else:
            answer_text = _parse_openai_chat_response(data)
    except ValueError as exc:
        logger.warning("[Step4] Ollama returned unusable response: %s", exc)
        elapsed = (time.perf_counter() - start) * 1000
        return _skipped_result(prompt_result, "empty_response", no_result_message, model_name, elapsed)

    except Exception as exc:
        logger.error("[Step4] Failed to parse Ollama response: %s", exc)
        elapsed = (time.perf_counter() - start) * 1000
        return _skipped_result(prompt_result, "generation_error", no_result_message, model_name, elapsed)

    answer_text = _ensure_bullet_readability(answer_text, prompt_result.format_type)

    elapsed = (time.perf_counter() - start) * 1000

    logger.info(
        "[Step4] Generated answer: model=%s latency=%.0fms answer_len=%d no_think=%s",
        model_name,
        elapsed,
        len(answer_text),
        no_think,
    )

    return AnswerGeneratorResult(
        answer_text=answer_text,
        was_generated=True,
        skip_reason=None,
        model_used=model_name,
        latency_ms=elapsed,
        prompt_token_estimate=prompt_token_estimate,
        no_think_injected=no_think,
        prompt_result=prompt_result,
    )
