#!/usr/bin/env python3
"""Smoke test for Step 5 - Citations and Faithfulness.

Run from the ai_server directory:
    python tests/smoke_step5.py

No Ollama or Qdrant required. This script uses mock chunk objects only.
"""
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.agents.config.agent_config_loader import load_agents_config
from ai.pipeline.step5a_citation_builder import run_citation_builder
from ai.pipeline.step5b_faithfulness_check import run_faithfulness_check


@dataclass
class MockChunk:
    chunk_id: str
    chunk_text: str
    score: float
    doc_id: str
    source_filename: str
    category: str
    section_heading: str
    page_number: int | None
    extraction_method: str
    upload_date: str | None
    chunk_index: int


def test_config_loader() -> None:
    cfg = load_agents_config()
    assert cfg.citation_builder.staleness_threshold_days == 180
    assert cfg.citation_builder.max_citations_in_response == 5
    assert cfg.faithfulness_check.enabled is True
    assert cfg.faithfulness_check.penalty_low > 0


def test_citation_builder_dedupes_and_ranks() -> None:
    chunks = [
        MockChunk(
            chunk_id="chunk-1",
            chunk_text="First SOP chunk.",
            score=0.72,
            doc_id="doc-a",
            source_filename="MPG_USA_Logistics_Claims_SOP.pdf",
            category="sop",
            section_heading="3.2 Shortage Claims Procedure",
            page_number=4,
            extraction_method="text_extraction",
            upload_date="2026-01-15",
            chunk_index=3,
        ),
        MockChunk(
            chunk_id="chunk-2",
            chunk_text="Second SOP chunk.",
            score=0.84,
            doc_id="doc-a",
            source_filename="MPG_USA_Logistics_Claims_SOP.pdf",
            category="sop",
            section_heading="3.2 Shortage Claims Procedure",
            page_number=4,
            extraction_method="text_extraction",
            upload_date="2026-01-15",
            chunk_index=5,
        ),
        MockChunk(
            chunk_id="chunk-3",
            chunk_text="Carrier agreement chunk.",
            score=0.79,
            doc_id="doc-b",
            source_filename="Carrier_Liability_DHL_Agreement.pdf",
            category="compliance",
            section_heading="Liability",
            page_number=2,
            extraction_method="ocr",
            upload_date="2026-02-01",
            chunk_index=9,
        ),
    ]

    result = run_citation_builder("Use the shortage process.", chunks)

    assert result.citation_method == "metadata"
    assert len(result.citations) == 2
    assert result.citations[0].source_filename == "MPG_USA_Logistics_Claims_SOP.pdf"
    assert result.citations[0].score_pct == 84
    assert result.citations[0].chunk_indices == [3, 5]
    assert result.ocr_sources_present is True
    assert "---\n**Sources**" in result.cited_answer
    assert "[SOURCE 1] MPG_USA_Logistics_Claims_SOP.pdf" in result.cited_answer


def test_faithfulness_flags_suspicious_figure() -> None:
    chunks = [
        MockChunk(
            chunk_id="chunk-1",
            chunk_text="The standard claim threshold is $500.",
            score=0.80,
            doc_id="doc-a",
            source_filename="SOP.pdf",
            category="sop",
            section_heading="Claims",
            page_number=1,
            extraction_method="text_extraction",
            upload_date=None,
            chunk_index=1,
        )
    ]

    result = run_faithfulness_check("The claim threshold is $99,999.", chunks)

    assert result.passed is False
    assert "$99,999" in result.suspicious_figures
    assert result.confidence_penalty > 0.0
    assert result.caution_message


def test_faithfulness_accepts_verified_figure() -> None:
    chunks = [
        MockChunk(
            chunk_id="chunk-1",
            chunk_text="The standard claim threshold is $500.",
            score=0.80,
            doc_id="doc-a",
            source_filename="SOP.pdf",
            category="sop",
            section_heading="Claims",
            page_number=1,
            extraction_method="text_extraction",
            upload_date=None,
            chunk_index=1,
        )
    ]

    result = run_faithfulness_check("The claim threshold is $500.", chunks)

    assert result.passed is True
    assert result.suspicious_figures == []
    assert result.confidence_penalty == 0.0


def main() -> None:
    tests = [
        test_config_loader,
        test_citation_builder_dedupes_and_ranks,
        test_faithfulness_flags_suspicious_figure,
        test_faithfulness_accepts_verified_figure,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("Step 5 smoke test passed.")


if __name__ == "__main__":
    main()
