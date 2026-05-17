#!/usr/bin/env python3
"""Regression tests for the layered system prompt architecture.

These tests pin the key behavioral rules of the final-answer system prompt so
that future edits do not silently reintroduce inline source markers, strip the
evidence contract, or lose citation discipline.
"""
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from ai.pipeline.prompts.system_prompts import get_system_prompt
from ai.config.company_profile import load_company_profile


_ALL_STYLES = ("direct", "procedural", "comparative", "exploratory")


def test_no_inline_source_markers_in_any_style_prompt() -> None:
    for style in _ALL_STYLES:
        prompt = get_system_prompt(style)
        # The rule itself mentions [SOURCE 1] / [SOURCE 2] as disallowed markers,
        # so those bracketed strings are expected to appear exactly once in the
        # output-discipline block — as the ban example. They must not reappear
        # as inline citations in any style's formatting or skeleton.
        assert prompt.count("[SOURCE 1]") <= 1, (
            f"Style {style!r} prompt contains inline [SOURCE 1] markers"
        )
        assert prompt.count("[SOURCE 2]") <= 1, (
            f"Style {style!r} prompt contains inline [SOURCE 2] markers"
        )


def test_universal_evidence_contract_phrases_present() -> None:
    required_phrases = [
        "evidence-controlled answer composer",
        "SOURCE DOCUMENTS section is the only authority",
        "Do not use outside knowledge",
        "not specified in",
        "Missing-data protocol",
        "Multi-part requests",
        "Do not merge rules from different source sections",
    ]
    for style in _ALL_STYLES:
        prompt = get_system_prompt(style)
        for phrase in required_phrases:
            assert phrase in prompt, (
                f"Style {style!r} prompt missing required phrase: {phrase!r}"
            )


def test_output_discipline_citation_rules_present() -> None:
    required_phrases = [
        "Do not include inline source markers",
        'End your answer with a "Sources:" section',
        "AVAILABLE SOURCE FILENAMES",
        "Do not invent filenames",
    ]
    for style in _ALL_STYLES:
        prompt = get_system_prompt(style)
        for phrase in required_phrases:
            assert phrase in prompt, (
                f"Style {style!r} prompt missing citation-discipline phrase: {phrase!r}"
            )


def test_universal_blocks_shared_verbatim_across_styles() -> None:
    """The role, contract, and output-discipline blocks must be identical across all styles."""
    profile = load_company_profile()
    anchor_phrases = [
        # Role anchor
        f"evidence-controlled answer composer for {profile.company.legal_name}",
        # Domain context anchor
        profile.company.domain_summary,
        # Evidence contract anchor
        "SOURCE DOCUMENTS section is the only authority",
        # Output discipline anchor
        "Do not include inline source markers",
    ]
    baseline = get_system_prompt("direct")
    for style in _ALL_STYLES:
        prompt = get_system_prompt(style)
        for phrase in anchor_phrases:
            assert phrase in prompt, f"Style {style!r} missing shared anchor: {phrase!r}"
            # Identical occurrence count across styles guards against drift
            assert prompt.count(phrase) == baseline.count(phrase), (
                f"Style {style!r} has diverging count for shared anchor: {phrase!r}"
            )


def test_style_overlays_carry_expected_formatting_signatures() -> None:
    direct = get_system_prompt("direct")
    procedural = get_system_prompt("procedural")
    comparative = get_system_prompt("comparative")
    exploratory = get_system_prompt("exploratory")

    assert "Answer style: DIRECT" in direct
    assert "Use bullet points" in direct
    assert "Do not write prose paragraphs" in direct

    assert "Answer style: PROCEDURAL" in procedural
    assert "numbered sequential steps" in procedural

    assert "Answer style: COMPARATIVE" in comparative
    assert "markdown table or as clearly labeled sections" in comparative

    assert "Answer style: EXPLORATORY" in exploratory
    assert "well-structured paragraphs" in exploratory


def test_unknown_style_falls_back_to_exploratory_overlay() -> None:
    unknown = get_system_prompt("not-a-real-style")
    exploratory = get_system_prompt("exploratory")
    assert unknown == exploratory

    none_prompt = get_system_prompt(None)
    assert none_prompt == exploratory


def test_all_styles_produce_non_empty_prompts() -> None:
    for style in _ALL_STYLES:
        prompt = get_system_prompt(style)
        assert isinstance(prompt, str)
        assert len(prompt) > 500, f"Style {style!r} prompt suspiciously short"


def test_system_prompt_uses_shared_company_profile_not_legacy_branding() -> None:
    profile = load_company_profile()
    prompt = get_system_prompt("direct")
    assert profile.company.legal_name in prompt
    assert "MPG USA INC" not in prompt


def test_no_stale_grounding_contract_header() -> None:
    """The old '_GROUNDING_CONTRACT' addendum is absorbed into the universal blocks."""
    for style in _ALL_STYLES:
        prompt = get_system_prompt(style)
        assert "Additional grounding contract" not in prompt, (
            f"Style {style!r} still carries the old addendum header"
        )


if __name__ == "__main__":
    tests = [
        test_no_inline_source_markers_in_any_style_prompt,
        test_universal_evidence_contract_phrases_present,
        test_output_discipline_citation_rules_present,
        test_universal_blocks_shared_verbatim_across_styles,
        test_style_overlays_carry_expected_formatting_signatures,
        test_unknown_style_falls_back_to_exploratory_overlay,
        test_all_styles_produce_non_empty_prompts,
        test_system_prompt_uses_shared_company_profile_not_legacy_branding,
        test_no_stale_grounding_contract_header,
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
