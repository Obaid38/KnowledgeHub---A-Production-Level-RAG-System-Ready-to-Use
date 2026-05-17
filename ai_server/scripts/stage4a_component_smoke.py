"""Stage 4A component smoke test — run from ai_server/ directory.

Validates all Stage 1 components in isolation (no Celery, no API):
  chunker → signals → context_prefix → embeddings → qdrant_writer

Usage:
    python scripts/stage4a_component_smoke.py --collection general
    python scripts/stage4a_component_smoke.py --collection general --cleanup
    python scripts/stage4a_component_smoke.py --doc-id <uuid> --cleanup
"""

import argparse
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

# Ensure ai_server root is on sys.path regardless of invocation location
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Imports (after sys.path and dotenv are set)
# ---------------------------------------------------------------------------
from ai.ingestion.chunker import chunk_document  # noqa: E402
from ai.ingestion.context_prefix import build_enriched_text  # noqa: E402
from ai.ingestion.qdrant_writer import delete_document_chunks, upsert_chunks  # noqa: E402
from ai.ingestion.signals import extract_signals  # noqa: E402
from ai.embeddings.loader import embed_texts  # noqa: E402

# ---------------------------------------------------------------------------
# Synthetic test data
# ---------------------------------------------------------------------------
_SYNTHETIC_TEXT = """\
INTRODUCTION

This document outlines standard procedures for freight claims handling.
Step 1: Identify the damaged shipment upon receipt.
Step 2: Contact the claims manager at claims@example.com or 1-800-555-0199.
Step 3: Submit the claim form within 30 days of delivery.

1. CLAIMS PROCESS

All freight claims above $500 USD must be reviewed by the Claims Director.
Due by end of January 2026. Total estimated liability: $12,500.
Q2 2026 deadline applies for annual audit reconciliation.

2. ROLES AND RESPONSIBILITIES

Claims Manager: Reviews all claims above $1,000 and coordinates with FedEx.
Account Representative: Primary point of contact for all Walmart shipments.
Compliance Officer: Ensures adherence to carrier SLA requirements with DHL.
"""

_SYNTHETIC_TABLE_1 = (
    "Claims Summary Table:\n"
    "Claim ID: 001. Status: Open. Amount: $500. Carrier: FedEx.\n"
    "Claim ID: 002. Status: Closed. Amount: $1,200. Carrier: UPS.\n"
    "Claim ID: 003. Status: Pending. Amount: $750. Carrier: DHL."
)

_SYNTHETIC_TABLE_2 = (
    "Contact Directory:\n"
    "Name: Jane Smith. Role: Claims Manager. Email: jane@example.com.\n"
    "Name: Bob Lee. Role: Account Representative. Phone: 1-800-555-0100."
)

_SYNTHETIC_TABLES = [_SYNTHETIC_TABLE_1, _SYNTHETIC_TABLE_2]
_SYNTHETIC_TABLE_NAMES = ["Claims Summary Table", "Contact Directory"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4A component smoke test")
    parser.add_argument(
        "--collection",
        default="general",
        help="Qdrant collection name (default: general)",
    )
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Document UUID to use (generated if omitted)",
    )
    parser.add_argument(
        "--filename",
        default="stage4_component_test.txt",
        help="Filename label embedded in chunk payloads",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete all upserted chunks after the test (requires --doc-id or previous run)",
    )
    args = parser.parse_args()

    doc_id = args.doc_id or str(uuid.uuid4())
    collection = args.collection
    filename = args.filename

    print(f"\n=== Stage 4A Component Smoke Test ===")
    print(f"doc_id     : {doc_id}")
    print(f"collection : {collection}")
    print(f"filename   : {filename}\n")

    # ------------------------------------------------------------------
    # Cleanup-only mode
    # ------------------------------------------------------------------
    if args.cleanup and args.doc_id:
        print(f"[Cleanup] Deleting chunks for doc_id={doc_id} from '{collection}'...")
        delete_document_chunks(collection, doc_id)
        print("[Cleanup] Done.\n")
        return

    # ------------------------------------------------------------------
    # Step 1: Chunking
    # ------------------------------------------------------------------
    print("--- Step 1: Chunking ---")
    chunks = chunk_document(
        clean_text=_SYNTHETIC_TEXT,
        serialized_tables=_SYNTHETIC_TABLES,
        table_names=_SYNTHETIC_TABLE_NAMES,
        headings=[],
        collection=collection,
    )
    text_chunks = [c for c in chunks if not c.is_table]
    table_chunks = [c for c in chunks if c.is_table]
    print(f"  total chunks     : {len(chunks)}")
    print(f"  text chunks      : {len(text_chunks)}")
    print(f"  table chunks     : {len(table_chunks)}")

    # Assertion: non-zero chunks, correct table count
    assert len(chunks) > 0, "FAIL: chunk_document returned 0 chunks"
    assert len(table_chunks) == len(_SYNTHETIC_TABLES), (
        f"FAIL: expected {len(_SYNTHETIC_TABLES)} table chunks, got {len(table_chunks)}"
    )
    print("  [PASS] chunk assertions\n")

    # ------------------------------------------------------------------
    # Step 2: Signal extraction
    # ------------------------------------------------------------------
    print("--- Step 2: Signal Extraction ---")
    signals_list = []
    for chunk in chunks:
        sig = extract_signals(chunk.text)
        # Integration layer: set table signals
        if chunk.is_table:
            sig.has_table_data = True
            sig.table_name = chunk.table_name
        signals_list.append(sig)

    # Quick sanity: at least one chunk should have monetary/date signals
    any_monetary = any(s.has_monetary_figures for s in signals_list)
    any_dates = any(s.has_dates for s in signals_list)
    any_contact = any(s.has_contact_info for s in signals_list)
    print(f"  any_monetary     : {any_monetary}")
    print(f"  any_dates        : {any_dates}")
    print(f"  any_contact      : {any_contact}")
    assert any_monetary, "FAIL: expected at least one chunk with monetary figures"
    assert any_dates, "FAIL: expected at least one chunk with dates"
    print("  [PASS] signal assertions\n")

    # ------------------------------------------------------------------
    # Step 3: Context prefix enrichment
    # ------------------------------------------------------------------
    print("--- Step 3: Context Prefix Enrichment ---")
    enriched_texts = []
    for chunk in chunks:
        enriched = build_enriched_text(
            chunk_text=chunk.text,
            filename=filename,
            heading=chunk.heading,
            table_name=chunk.table_name,
            collection=collection,
            is_table=chunk.is_table,
        )
        enriched_texts.append(enriched)

    print(f"  enriched count   : {len(enriched_texts)}")
    # Verify prefix is prepended (config ENABLE_CONTEXTUAL_PREFIX=true by default)
    sample = enriched_texts[0]
    assert "[Document:" in sample, f"FAIL: expected prefix in enriched text, got: {sample[:80]}"
    print(f"  sample prefix    : {sample.splitlines()[0]}")
    print("  [PASS] prefix assertions\n")

    # ------------------------------------------------------------------
    # Step 4: Embedding
    # ------------------------------------------------------------------
    print("--- Step 4: Embedding ---")
    print("  (Loading model — may take a moment on first run...)")
    vectors = embed_texts(enriched_texts)
    print(f"  vector count     : {len(vectors)}")
    print(f"  vector dim       : {len(vectors[0]) if vectors else 'N/A'}")

    assert len(vectors) == len(chunks), (
        f"FAIL: expected {len(chunks)} vectors, got {len(vectors)}"
    )
    print("  [PASS] embedding assertions\n")

    # ------------------------------------------------------------------
    # Step 5: Qdrant upsert
    # ------------------------------------------------------------------
    print("--- Step 5: Qdrant Upsert ---")
    chunks_with_meta = []
    for chunk, sig in zip(chunks, signals_list):
        sig_dict = asdict(sig)
        # Remove table_name from signals dict — it's stored as a top-level payload key
        sig_dict.pop("table_name", None)
        chunks_with_meta.append({
            "text": chunk.text,
            "heading": chunk.heading,
            "is_table": chunk.is_table,
            "table_name": chunk.table_name,
            "chunk_index": chunk.chunk_index,
            "signals": sig_dict,
        })

    upserted_count = upsert_chunks(
        collection=collection,
        doc_id=doc_id,
        filename=filename,
        chunks_with_meta=chunks_with_meta,
        vectors=vectors,
    )
    print(f"  upserted count   : {upserted_count}")

    assert upserted_count == len(chunks), (
        f"FAIL: expected {len(chunks)} upserted, got {upserted_count}"
    )
    print("  [PASS] upsert assertions\n")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("=== Stage 4A PASSED ===")
    print(f"  chunk_count      : {len(chunks)}")
    print(f"  text_chunk_count : {len(text_chunks)}")
    print(f"  table_chunk_count: {len(table_chunks)}")
    print(f"  vector_count     : {len(vectors)}")
    print(f"  upserted_count   : {upserted_count}")
    print(f"  doc_id           : {doc_id}")
    print()
    print(f"To clean up: python scripts/stage4a_component_smoke.py --collection {collection} --doc-id {doc_id} --cleanup")
    print()

    # ------------------------------------------------------------------
    # Optional inline cleanup (--cleanup without --doc-id)
    # ------------------------------------------------------------------
    if args.cleanup:
        print(f"[Cleanup] Deleting {upserted_count} chunk(s) for doc_id={doc_id}...")
        delete_document_chunks(collection, doc_id)
        print("[Cleanup] Done.\n")


if __name__ == "__main__":
    main()
