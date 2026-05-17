"""Stage 1 smoke test — run from ai_server/ directory.

Usage:
    python scripts/stage1_smoke_test.py --file C:/path/to/sample.pdf --upload-minio --user-category sop
    python scripts/stage1_smoke_test.py --file C:/path/to/sample.docx
"""

import argparse
import sys
import uuid
from pathlib import Path

# Ensure ai_server root is on sys.path regardless of where the script is invoked from
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from ai.ingestion.pipeline_stage1 import run_stage1_pipeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1 smoke test")
    parser.add_argument("--file", required=True, help="Path to file to test extraction on")
    parser.add_argument(
        "--upload-minio",
        action="store_true",
        help="Upload to MinIO, download bytes back, assert equality, then delete",
    )
    parser.add_argument(
        "--user-category",
        default=None,
        help="Optional user category prefix for MinIO path (e.g. sop, finance)",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    file_bytes = file_path.read_bytes()
    filename = file_path.name

    print(f"\n=== Stage 1 Smoke Test: {filename} ===\n")

    try:
        result = run_stage1_pipeline(file_bytes, filename)
    except Exception as exc:
        print(f"FAILED during run_stage1_pipeline: {exc}", file=sys.stderr)
        raise

    ext = result.extraction
    cr = result.clean_result

    print(f"{'filename':<30} {filename}")
    print(f"{'extraction_method':<30} {ext.extraction_method}")
    print(f"{'page_count':<30} {ext.page_count}")
    print(f"{'text_chars':<30} {len(ext.text)}")
    print(f"{'headings_count':<30} {len(cr.headings)}")
    print(f"{'table_count_raw':<30} {len(ext.raw_tables)}")
    print(f"{'table_count_serialized':<30} {len(result.serialized_tables)}")
    print(f"{'carriers_detected':<30} {cr.carriers_detected}")
    print(f"{'customers_detected':<30} {cr.customers_detected}")
    print(f"{'has_monetary_data':<30} {cr.has_monetary_data}")
    print(f"{'has_timeline_data':<30} {cr.has_timeline_data}")

    if cr.headings:
        print("\nHeadings (first 5):")
        for h in cr.headings[:5]:
            print(f"  - {h}")

    if result.serialized_tables:
        print("\nSerialized tables (first 1, truncated):")
        t = result.serialized_tables[0]
        preview = t.text[:300] + ("..." if len(t.text) > 300 else "")
        print(f"  [{t.table_name}] {t.row_count} rows\n  {preview}")

    if args.upload_minio:
        print("\n--- MinIO roundtrip test ---")
        from ai.ingestion.minio_client import (
            delete_file_from_minio,
            download_file_from_minio,
            upload_file_to_minio,
        )

        doc_id = str(uuid.uuid4())
        print(f"doc_id: {doc_id}")

        minio_path = upload_file_to_minio(file_bytes, doc_id, filename, args.user_category)
        print(f"Uploaded to: {minio_path}")

        downloaded = download_file_from_minio(minio_path)
        if downloaded != file_bytes:
            raise AssertionError(
                f"BYTE MISMATCH: uploaded {len(file_bytes)} bytes, "
                f"downloaded {len(downloaded)} bytes"
            )
        print(f"Byte equality check: PASSED ({len(file_bytes)} bytes)")

        delete_file_from_minio(minio_path)
        print(f"Deleted from MinIO: {minio_path}")

    print("\n=== Stage 1 PASSED ===\n")


if __name__ == "__main__":
    main()
