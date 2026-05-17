import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct, SparseVector

from ai.config import HYBRID_SEARCH_ENABLED, QDRANT_HOST, QDRANT_PORT

logger = logging.getLogger("knowledge_hub.qdrant_writer")

_qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return the module-level singleton QdrantClient, creating it on first call."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        logger.info("[QdrantWriter] Connected to Qdrant at %s:%d", QDRANT_HOST, QDRANT_PORT)
    return _qdrant_client


def upsert_chunks(
    collection: str,
    doc_id: str,
    filename: str,
    category: str,
    chunks_with_meta: list[dict],
    vectors: list[list[float]],
    sparse_vectors: list | None = None,
) -> int:
    """Upsert chunks + vectors into the Qdrant collection.

    Each chunk dict must contain:
        text, heading, is_table, table_name, chunk_index, signals (dict)

    ``category`` is stored as a searchable payload field so retrieval can
    apply a Qdrant payload filter when the user scopes their query by category.

    Point IDs are deterministic: uuid5(NAMESPACE_URL, "{doc_id}/{chunk_index}")
    — safe for idempotent re-upserts on retry.

    When ``sparse_vectors`` is provided (HYBRID_SEARCH_ENABLED=true), each
    point is stored with named vectors:
        vector={
            "dense": <float list>,
            "bm25": SparseVector(indices=[...], values=[...]),
        }
    The collection must have been created with a matching sparse_vectors_config.

    When ``sparse_vectors`` is None, the vector shape depends on HYBRID_SEARCH_ENABLED.
    HYBRID_SEARCH_ENABLED=false uses the legacy single-vector format for
    older dense-only collections. When HYBRID_SEARCH_ENABLED=true, the code uses
    vector={"dense": <float list>} so dense fallback remains compatible with
    the hybrid collection schema.

    Returns the number of points upserted.
    """
    if len(chunks_with_meta) != len(vectors):
        raise ValueError(
            f"chunks_with_meta length {len(chunks_with_meta)} != vectors length {len(vectors)}"
        )

    use_hybrid = (
        sparse_vectors is not None
        and len(sparse_vectors) == len(vectors)
    )

    client = get_qdrant_client()
    points: list[PointStruct] = []

    for i, (chunk, dense_vec) in enumerate(zip(chunks_with_meta, vectors)):
        chunk_index = chunk["chunk_index"]
        # Deterministic UUID so the same chunk always maps to the same point ID
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}/{chunk_index}"))

        # Flatten signals dict into the payload (booleans + entity_mentions list)
        signals: dict = chunk.get("signals", {})

        payload: dict = {
            "doc_id":      doc_id,
            "filename":    filename,
            "category":    category,        # payload filter field — replaces collection routing
            "doc_type":    chunk.get("doc_type", "narrative"),  # auto-detected structural type
            "chunk_index": chunk_index,
            "text":        chunk["text"],
            "heading":     chunk.get("heading"),
            "is_table":    chunk.get("is_table", False),
            "table_name":  chunk.get("table_name"),
            # Flattened signal fields
            "has_monetary_figures": signals.get("has_monetary_figures", False),
            "has_dates":            signals.get("has_dates", False),
            "has_deadlines":        signals.get("has_deadlines", False),
            "has_steps":            signals.get("has_steps", False),
            "has_contact_info":     signals.get("has_contact_info", False),
            "has_roles":            signals.get("has_roles", False),
            "entity_mentions":      signals.get("entity_mentions", []),
            "has_table_data":       signals.get("has_table_data", False),
        }

        if use_hybrid:
            sv = sparse_vectors[i]
            point = PointStruct(
                id=point_id,
                vector={
                    "dense": dense_vec,
                    "bm25": SparseVector(
                        indices=list(sv.indices),
                        values=list(sv.values),
                    ),
                },
                payload=payload,
            )
        elif HYBRID_SEARCH_ENABLED:
            point = PointStruct(id=point_id, vector={"dense": dense_vec}, payload=payload)
        else:
            point = PointStruct(id=point_id, vector=dense_vec, payload=payload)

        points.append(point)

    client.upsert(collection_name=collection, points=points, wait=True)
    mode = (
        "hybrid dense+bm25"
        if use_hybrid
        else "hybrid dense-only"
        if HYBRID_SEARCH_ENABLED
        else "dense-only"
    )
    logger.info(
        "[QdrantWriter] Upserted %d point(s) into collection '%s' for doc_id=%s category=%s mode=%s",
        len(points),
        collection,
        doc_id,
        category,
        mode,
    )
    return len(points)


def delete_document_chunks(collection: str, doc_id: str) -> None:
    """Delete all Qdrant points that belong to the given doc_id."""
    client = get_qdrant_client()
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
        wait=True,
    )
    logger.info(
        "[QdrantWriter] Deleted chunks for doc_id=%s from collection '%s'",
        doc_id,
        collection,
    )
