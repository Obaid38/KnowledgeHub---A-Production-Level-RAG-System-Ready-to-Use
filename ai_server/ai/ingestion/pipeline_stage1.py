from dataclasses import dataclass

from ai.ingestion.cleaner import CleanResult, clean_and_parse
from ai.ingestion.extractor import ExtractionResult, extract
from ai.ingestion.table_serializer import (
    SerializedTable,
    detect_table_names_from_headings,
    serialize_tables,
)


@dataclass
class Stage1PipelineResult:
    extraction: ExtractionResult
    clean_result: CleanResult
    serialized_tables: list[SerializedTable]
    table_names: list[str]


def run_stage1_pipeline(file_bytes: bytes, filename: str) -> Stage1PipelineResult:
    """Run the complete Stage 1 pipeline: extract → clean → detect table names → serialize tables.

    This is the single integration entry point that Stage 2 (Celery task) calls.
    Do not duplicate this logic elsewhere.
    """
    extraction = extract(file_bytes, filename)
    clean_result = clean_and_parse(extraction.text)
    table_names = detect_table_names_from_headings(
        clean_result.headings, len(extraction.raw_tables)
    )
    serialized_tables = serialize_tables(extraction.raw_tables, table_names)
    return Stage1PipelineResult(
        extraction=extraction,
        clean_result=clean_result,
        serialized_tables=serialized_tables,
        table_names=table_names,
    )
