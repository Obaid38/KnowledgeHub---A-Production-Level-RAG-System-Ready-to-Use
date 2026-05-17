#!/usr/bin/env python3
"""One-time collection migration script: recreate Qdrant collection for hybrid search.

Run this script ONCE before re-ingesting all documents when enabling hybrid
BM25 + dense search (HYBRID_SEARCH_ENABLED=true).

What it does:
  1. Deletes the existing 'documents' collection (or whatever QDRANT_COLLECTION is).
  2. Creates a new collection with named dense + BM25 sparse vector config.
  3. Prints re-ingest instructions.

Prerequisites:
  - Qdrant running (locally on port 6333 or at QDRANT_URL).
  - No active ingest jobs in progress (stop Celery workers first).
  - Back up any data you need — deletion is irreversible.

After running this script:
  - Re-ingest all documents via the frontend or:
      python -c "import httpx; httpx.post('http://localhost:8000/api/ingest-documents', json=[...])"
  - Set HYBRID_SEARCH_ENABLED=true in your .env and restart the API.

Usage:
    cd ai_server
    python scripts/recreate_collection_hybrid.py
    python scripts/recreate_collection_hybrid.py --dry-run
    python scripts/recreate_collection_hybrid.py --env-file /path/to/.env
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure ai_server root is importable
AI_SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_SERVER_ROOT))


def _load_env(explicit_path: str | None) -> None:
    """Minimal dotenv loader — keeps the script free from python-dotenv dep."""
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    candidates += [
        AI_SERVER_ROOT.parent / ".env",
        AI_SERVER_ROOT / ".env",
    ]
    for path in candidates:
        if path.is_file():
            with path.open(encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key:
                        os.environ.setdefault(key, val)
            print(f"[env] Loaded {path}")
            return
    print("[env] No .env file found — using system environment variables only")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recreate Qdrant collection for hybrid search")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without making changes")
    parser.add_argument("--env-file", help="Path to .env file (optional)")
    args = parser.parse_args()

    _load_env(args.env_file)

    # Import after env is loaded
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, SparseIndexParams, SparseVectorParams, VectorParams

    from ai.config import EMBEDDING_DIM, QDRANT_COLLECTION, QDRANT_DISTANCE_METRIC, QDRANT_URL

    distance_map = {
        "cosine": Distance.COSINE,
        "dot": Distance.DOT,
        "euclid": Distance.EUCLID,
        "manhattan": Distance.MANHATTAN,
    }
    distance = distance_map.get(QDRANT_DISTANCE_METRIC.lower(), Distance.COSINE)

    print()
    print("=" * 60)
    print("  Qdrant Hybrid Collection Recreation")
    print("=" * 60)
    print(f"  Qdrant URL     : {QDRANT_URL}")
    print(f"  Collection     : {QDRANT_COLLECTION}")
    print(f"  Embedding dim  : {EMBEDDING_DIM}")
    print(f"  Distance metric: {distance}")
    print(f"  Dry run        : {args.dry_run}")
    print("=" * 60)
    print()

    if not args.dry_run:
        confirm = input(
            f"  This will DELETE '{QDRANT_COLLECTION}' and recreate it.\n"
            "  All existing vectors will be lost. You must re-ingest afterwards.\n\n"
            "  Type 'yes' to continue, anything else to abort: "
        ).strip().lower()
        if confirm != "yes":
            print("  Aborted.")
            return
        print()

    client = QdrantClient(url=QDRANT_URL)

    # Check current state
    existing = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION in existing:
        info = client.get_collection(QDRANT_COLLECTION)
        point_count = getattr(info, "points_count", "unknown")
        print(f"  Found existing collection '{QDRANT_COLLECTION}' with {point_count} points.")
        if args.dry_run:
            print(f"  [dry-run] Would delete '{QDRANT_COLLECTION}'.")
        else:
            client.delete_collection(QDRANT_COLLECTION)
            print(f"  Deleted '{QDRANT_COLLECTION}'.")
    else:
        print(f"  Collection '{QDRANT_COLLECTION}' does not exist — will create fresh.")

    # Create new collection with hybrid schema
    new_vectors_config = {"dense": VectorParams(size=EMBEDDING_DIM, distance=distance)}
    new_sparse_config = {"bm25": SparseVectorParams(index=SparseIndexParams(on_disk=False))}

    if args.dry_run:
        print(f"  [dry-run] Would create '{QDRANT_COLLECTION}' with:")
        print(f"    vectors_config       = {{\"dense\": VectorParams(size={EMBEDDING_DIM}, distance={distance})}}")
        print(f"    sparse_vectors_config= {{\"bm25\": SparseVectorParams(on_disk=False)}}")
    else:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=new_vectors_config,
            sparse_vectors_config=new_sparse_config,
        )
        # Verify
        info = client.get_collection(QDRANT_COLLECTION)
        print(f"  Created '{QDRANT_COLLECTION}' successfully.")
        print(f"  Points count: {getattr(info, 'points_count', 0)}")

    print()
    print("=" * 60)
    print("  Next steps:")
    print()
    print("  1. Set HYBRID_SEARCH_ENABLED=true in your .env file.")
    print()
    print("  2. Re-ingest all documents via the frontend or API:")
    print("       POST /api/ingest-documents")
    print()
    print("  3. Restart the API and Celery worker:")
    print("       python -m uvicorn app.main:app --reload --port 8000")
    print()
    print("  4. Verify the schema:")
    print(f"       curl http://localhost:6333/collections/{QDRANT_COLLECTION} | python -m json.tool")
    print()
    print("  5. Run retrieval verification:")
    print("       python scripts/debug_retrieval.py \\")
    print("         --input docs/tested_queries_sop_30.txt \\")
    print("         --category sop --reranker")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
