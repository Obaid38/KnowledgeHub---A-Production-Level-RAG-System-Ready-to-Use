import logging

from ai.config import ENABLE_CONTEXTUAL_PREFIX

logger = logging.getLogger("knowledge_hub.context_prefix")


def build_enriched_text(
    chunk_text: str,
    filename: str,
    heading: str | None,
    table_name: str | None,
    category: str,
    is_table: bool,
    enable_prefix: bool | None = None,
) -> str:
    """Return enriched text for embedding.

    When ENABLE_CONTEXTUAL_PREFIX (or the override ``enable_prefix``) is False,
    the raw chunk_text is returned unchanged.

    When enabled:
    - Text chunk:  ``[Document: X] [Section: Y] [Category: Z]\\n{chunk_text}``
    - Table chunk: ``[Document: X] [Table: Y]   [Category: Z]\\n{chunk_text}``

    The ``category`` parameter is stored in the prefix so the embedding model
    can distinguish chunks by document type during semantic search.
    """
    active = enable_prefix if enable_prefix is not None else ENABLE_CONTEXTUAL_PREFIX
    if not active:
        return chunk_text

    prefix = _build_prefix(filename, heading, table_name, category, is_table)
    enriched = prefix + "\n" + chunk_text
    logger.debug("[ContextPrefix] prefix=%r", prefix)
    return enriched


def _build_prefix(
    filename: str,
    heading: str | None,
    table_name: str | None,
    category: str,
    is_table: bool,
) -> str:
    """Build the metadata prefix string for a single chunk."""
    doc_tag      = f"[Document: {filename}]"
    category_tag = f"[Category: {category}]"

    if is_table:
        name        = table_name if table_name else "Unknown"
        section_tag = f"[Table: {name}]"
    else:
        section     = heading if heading else "N/A"
        section_tag = f"[Section: {section}]"

    return f"{doc_tag} {section_tag} {category_tag}"
