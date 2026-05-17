#!/usr/bin/env python3
"""RAG Retrieval Debug Tool — retrieve chunks for a batch of queries.

Hits the retrieval layer directly (no LLM, no uvicorn).
Requires: Qdrant running, embedding backend (Ollama or sentence-transformers) ready.

Usage:
    cd ai_server
    python scripts/debug_retrieval.py --input docs/tested_queries.txt
    python scripts/debug_retrieval.py --input "What are the escalation levels?"
    python scripts/debug_retrieval.py --input docs/tested_queries.txt --top-k 20
    python scripts/debug_retrieval.py --input docs/tested_queries.txt --category sop --top-k 30
    python scripts/debug_retrieval.py --input docs/tested_queries.txt --category sop legal --threshold 0.3
    python scripts/debug_retrieval.py --input "What are the escalation levels?" --reranker
    python scripts/debug_retrieval.py --env-file /workspace/repo/.env --input "What are the escalation levels?" --reranker
    python scripts/debug_retrieval.py --via-api --input "What are the escalation levels?" --reranker

Input can be a file path or a literal query string. File format:
    What are the escalation levels?
    # this is a comment
    Who handles theft incidents?

Output: a timestamped JSON report + a human-readable summary printed to stdout.
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure ai_server root is importable
AI_SERVER_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = AI_SERVER_ROOT.parent
sys.path.insert(0, str(AI_SERVER_ROOT))


def _preparse_env_file(argv: list[str]) -> str | None:
    """Read --env-file before importing app config."""
    for idx, value in enumerate(argv):
        if value == "--env-file" and idx + 1 < len(argv):
            return argv[idx + 1]
        if value.startswith("--env-file="):
            return value.split("=", 1)[1]
    return None


def _load_env_file(path: Path, override: bool = False) -> bool:
    """Minimal dotenv loader so this script works without python-dotenv."""
    if not path.is_file():
        return False

    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key:
                if override:
                    os.environ[key] = value
                else:
                    os.environ.setdefault(key, value)
    return True


def _load_env() -> Path | None:
    """Load the first available project env file before config imports."""
    explicit = _preparse_env_file(sys.argv[1:]) or os.getenv("INSIGHTHUB_ENV_FILE")
    candidates = []
    if explicit:
        candidates.append((Path(explicit), True))
    candidates.extend([
        (PROJECT_ROOT / ".env", False),
        (AI_SERVER_ROOT / ".env", False),
        (Path.cwd() / ".env", False),
    ])

    seen: set[Path] = set()
    for candidate, override in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if _load_env_file(resolved, override=override):
            return resolved
    return None


LOADED_ENV_FILE = _load_env()

from ai.config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_BACKEND,
    EMBEDDING_DIM,
    EMBEDDING_QUERY_PREFIX,
    OLLAMA_EMBED_MODEL,
    OLLAMA_URL,
    QDRANT_COLLECTION,
    RERANKER_ENABLED,
    RETRIEVAL_SCORE_THRESHOLD,
    RETRIEVAL_TOP_K_PRE_RERANK,
    RETRIEVAL_TOP_K_POST_RERANK,
    USE_CATEGORY_CHUNKING,
    CATEGORY_CHUNK_CONFIG,
    QDRANT_URL,
)
from ai.retrieval.query_embedder import embed_query as native_embed_query
from ai.retrieval.result_models import RetrievedChunk

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("debug_retrieval")

SEP  = "=" * 80
THIN = "-" * 80
DEBUG_RERANKER_PRE_K = 50

_NATIVE_SEARCH_COLLECTION = None
_NATIVE_SEARCH_IMPORT_ATTEMPTED = False
_OLLAMA_EMBED_FALLBACK_LOGGED = False
_QDRANT_REST_FALLBACK_LOGGED = False


def embed_query(query_text: str) -> list[float]:
    """Embed a query with the app path, or stdlib Ollama fallback if needed."""
    global _OLLAMA_EMBED_FALLBACK_LOGGED
    try:
        return native_embed_query(query_text)
    except ModuleNotFoundError as exc:
        if exc.name != "httpx" or EMBEDDING_BACKEND != "ollama":
            raise

    if not _OLLAMA_EMBED_FALLBACK_LOGGED:
        logger.warning(
            "httpx is not installed in this Python environment; "
            "using Ollama REST fallback against %s",
            OLLAMA_URL,
        )
        _OLLAMA_EMBED_FALLBACK_LOGGED = True
    return embed_query_ollama_rest(query_text)


def embed_query_ollama_rest(query_text: str) -> list[float]:
    """Embed a single query through Ollama with only the standard library."""
    from urllib import error, request

    effective_query = f"{EMBEDDING_QUERY_PREFIX} {query_text}".strip() if EMBEDDING_QUERY_PREFIX else query_text
    url = f"{OLLAMA_URL.rstrip('/')}/api/embeddings"
    body = json.dumps({
        "model": OLLAMA_EMBED_MODEL,
        "prompt": effective_query,
    }).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code} at {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach Ollama at {url}: {exc}") from exc

    embedding = data.get("embedding")
    if not embedding:
        raise RuntimeError(f"Ollama returned no embedding for model={OLLAMA_EMBED_MODEL}: {data}")
    if len(embedding) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Ollama embedding dim={len(embedding)}, expected EMBEDDING_DIM={EMBEDDING_DIM}. "
            "Check OLLAMA_EMBED_MODEL and EMBEDDING_DIM in the env file."
        )
    return embedding


def search_collection(
    query_vector: list[float],
    collection: str,
    top_k: int,
    score_threshold: float,
    access_level_filter: str | None = None,
    category_filter: list[str] | None = None,
) -> tuple[list[RetrievedChunk], int]:
    """Search Qdrant via qdrant-client when installed, else via REST."""
    global _NATIVE_SEARCH_COLLECTION, _NATIVE_SEARCH_IMPORT_ATTEMPTED
    global _QDRANT_REST_FALLBACK_LOGGED

    if not _NATIVE_SEARCH_IMPORT_ATTEMPTED:
        _NATIVE_SEARCH_IMPORT_ATTEMPTED = True
        try:
            from ai.retrieval.qdrant_searcher import search_collection as native_search_collection

            _NATIVE_SEARCH_COLLECTION = native_search_collection
        except ModuleNotFoundError as exc:
            if exc.name != "qdrant_client":
                raise
            _NATIVE_SEARCH_COLLECTION = None

    if _NATIVE_SEARCH_COLLECTION is not None:
        return _NATIVE_SEARCH_COLLECTION(
            query_vector=query_vector,
            collection=collection,
            top_k=top_k,
            score_threshold=score_threshold,
            access_level_filter=access_level_filter,
            category_filter=category_filter,
        )

    if not _QDRANT_REST_FALLBACK_LOGGED:
        logger.warning(
            "qdrant-client is not installed in this Python environment; "
            "using Qdrant REST fallback against %s",
            QDRANT_URL,
        )
        _QDRANT_REST_FALLBACK_LOGGED = True

    return search_collection_rest(
        query_vector=query_vector,
        collection=collection,
        top_k=top_k,
        score_threshold=score_threshold,
        access_level_filter=access_level_filter,
        category_filter=category_filter,
    )


def search_collection_rest(
    query_vector: list[float],
    collection: str,
    top_k: int,
    score_threshold: float,
    access_level_filter: str | None = None,
    category_filter: list[str] | None = None,
) -> tuple[list[RetrievedChunk], int]:
    """Qdrant search fallback that needs only the Python standard library."""
    query_filter = build_qdrant_filter(access_level_filter, category_filter)

    passing_results = qdrant_query_points_rest(
        collection=collection,
        query_vector=query_vector,
        top_k=top_k,
        score_threshold=score_threshold,
        query_filter=query_filter,
        with_payload=True,
    )
    all_results = qdrant_query_points_rest(
        collection=collection,
        query_vector=query_vector,
        top_k=top_k,
        score_threshold=0.0,
        query_filter=query_filter,
        with_payload=False,
    )

    below_threshold_count = max(0, len(all_results) - len(passing_results))
    chunks = [map_rest_point(point, collection) for point in passing_results]
    return chunks, below_threshold_count


def build_qdrant_filter(
    access_level_filter: str | None,
    category_filter: list[str] | None,
) -> dict | None:
    """Build Qdrant REST filter payload matching qdrant_searcher.py."""
    must_conditions = []
    if category_filter:
        if len(category_filter) == 1:
            must_conditions.append({
                "key": "category",
                "match": {"value": category_filter[0]},
            })
        else:
            must_conditions.append({
                "key": "category",
                "match": {"any": category_filter},
            })

    if access_level_filter is not None:
        must_conditions.append({
            "key": "access_level",
            "match": {"value": access_level_filter},
        })

    return {"must": must_conditions} if must_conditions else None


def qdrant_query_points_rest(
    collection: str,
    query_vector: list[float],
    top_k: int,
    score_threshold: float,
    query_filter: dict | None,
    with_payload: bool,
) -> list[dict]:
    """Call Qdrant REST, trying the current query API then legacy search."""
    query_payload = {
        "query": query_vector,
        "limit": top_k,
        "score_threshold": score_threshold,
        "with_payload": with_payload,
        "with_vector": False,
    }
    if query_filter is not None:
        query_payload["filter"] = query_filter

    try:
        data = qdrant_post_json(f"/collections/{collection}/points/query", query_payload)
        return extract_qdrant_points(data)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "variant" not in msg and "not found" not in msg and "404" not in msg:
            raise

    search_payload = {
        "vector": query_vector,
        "limit": top_k,
        "score_threshold": score_threshold,
        "with_payload": with_payload,
        "with_vector": False,
    }
    if query_filter is not None:
        search_payload["filter"] = query_filter

    try:
        data = qdrant_post_json(f"/collections/{collection}/points/search", search_payload)
    except RuntimeError as exc:
        if "404" in str(exc):
            raise ValueError(f"Collection '{collection}' not found in Qdrant") from exc
        raise
    return extract_qdrant_points(data)


def qdrant_post_json(path: str, payload: dict) -> dict:
    """POST JSON to Qdrant using urllib so no extra dependency is needed."""
    from urllib import error, request

    url = f"{QDRANT_URL.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Qdrant HTTP {exc.code} at {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach Qdrant at {url}: {exc}") from exc


def extract_qdrant_points(data: dict) -> list[dict]:
    """Extract scored points from both Qdrant query and search responses."""
    result = data.get("result")
    if isinstance(result, dict) and isinstance(result.get("points"), list):
        return result["points"]
    if isinstance(result, list):
        return result
    return []


def map_rest_point(point: dict, collection: str) -> RetrievedChunk:
    """Map a Qdrant REST point to a RetrievedChunk."""
    payload = point.get("payload") or {}
    return RetrievedChunk(
        chunk_id=str(point.get("id", "")),
        chunk_text=payload.get("text", ""),
        score=float(point.get("score") or 0.0),
        doc_id=payload.get("doc_id", ""),
        source_filename=payload.get("filename", ""),
        category=payload.get("category", collection),
        section_heading=payload.get("heading") or "",
        page_number=payload.get("page_number", None),
        access_level=payload.get("access_level", "internal"),
        extraction_method=payload.get("extraction_method", ""),
        upload_date=payload.get("upload_date", ""),
        language=payload.get("language", "en"),
        chunk_index=payload.get("chunk_index", 0),
    )


def parse_queries(path: str) -> list[str]:
    """Read queries from a text file. Skip blanks and # comments."""
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                queries.append(stripped)
    return queries


def load_queries(input_value: str) -> tuple[list[str], str]:
    """Load queries from a file path, or treat --input as a literal query."""
    try:
        input_path = Path(input_value)
        if input_path.is_file():
            return parse_queries(str(input_path)), "file"
    except (OSError, ValueError):
        pass

    query = input_value.strip()
    return ([query] if query else []), "query"


def score_range(chunks: list) -> str:
    """Return a compact min-to-max vector score range for display/reporting."""
    if not chunks:
        return "none"
    return f"{chunks[-1].score:.4f} - {chunks[0].score:.4f}"


def chunk_records_from_chunks(chunks: list) -> list[dict]:
    """Convert RetrievedChunk objects into JSON/report-friendly records."""
    chunk_records = []
    for rank, c in enumerate(chunks, 1):
        chunk_records.append({
            "rank":            rank,
            "score":           round(c.score, 5),
            "rerank_score":    round(c.rerank_score, 5) if c.rerank_score is not None else None,
            "category":        c.category,
            "source_filename": c.source_filename,
            "section_heading": c.section_heading,
            "chunk_index":     c.chunk_index,
            "char_len":        len(c.chunk_text),
            "text_preview":    c.chunk_text[:300].replace("\n", " "),
            "text_full":       c.chunk_text,
        })
    return chunk_records


def chunk_records_from_api(chunks: list[dict]) -> list[dict]:
    """Convert /api/qa/retrieve-debug chunks into local report records."""
    chunk_records = []
    for rank, c in enumerate(chunks, 1):
        text = c.get("chunk_text") or ""
        rerank_score = c.get("rerank_score")
        chunk_records.append({
            "rank":            rank,
            "score":           round(float(c.get("score") or 0.0), 5),
            "rerank_score":    round(float(rerank_score), 5) if rerank_score is not None else None,
            "category":        c.get("category", ""),
            "source_filename": c.get("source_filename", ""),
            "section_heading": c.get("section_heading", ""),
            "chunk_index":     c.get("chunk_index", 0),
            "char_len":        len(text),
            "text_preview":    text[:300].replace("\n", " "),
            "text_full":       text,
        })
    return chunk_records


def score_range_from_records(chunks: list[dict]) -> str:
    """Return a compact vector score range for API chunk records."""
    if not chunks:
        return "none"
    scores = [float(c["score"]) for c in chunks]
    return f"{min(scores):.4f} - {max(scores):.4f}"


def retrieve_debug_endpoint_url(api_url: str) -> str:
    """Resolve a base API URL or direct endpoint URL to retrieve-debug."""
    cleaned = api_url.rstrip("/")
    if cleaned.endswith("/retrieve-debug"):
        return cleaned
    if cleaned.endswith("/api/qa"):
        return f"{cleaned}/retrieve-debug"
    return f"{cleaned}/api/qa/retrieve-debug"


def post_json(url: str, payload: dict, timeout_s: float = 300.0) -> dict:
    """POST JSON using urllib so --via-api also works in thin Python envs."""
    from urllib import error, request

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise RuntimeError(
                f"API endpoint not found at {url}. Pull this change on RunPod "
                "and restart the api service with `ihctl restart api`."
            ) from exc
        raise RuntimeError(f"API HTTP {exc.code} at {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach API at {url}: {exc}") from exc


def run_single_query_via_api(
    query: str,
    api_url: str,
    top_k: int,
    threshold: float,
    use_reranker: bool,
    reranker_top_k: int,
    category_filter: list[str] | None,
) -> dict:
    """Call the running FastAPI process so the reranker model is reused."""
    endpoint = retrieve_debug_endpoint_url(api_url)
    payload = {
        "query": query,
        "category_filter": category_filter,
        "top_k": top_k,
        "score_threshold": threshold,
        "use_reranker": use_reranker,
        "post_rerank_top_k": reranker_top_k,
    }
    api_result = post_json(endpoint, payload)

    initial_chunk_records = chunk_records_from_api(api_result.get("initial_chunks") or [])
    reranked_chunk_records = chunk_records_from_api(api_result.get("reranked_chunks") or [])
    chunk_records = chunk_records_from_api(api_result.get("chunks") or [])
    reranked = (
        bool(api_result.get("reranked"))
        or bool(reranked_chunk_records)
        or api_result.get("reranker_status") == "reranked"
    )
    if reranked and reranked_chunk_records:
        chunk_records = reranked_chunk_records

    return {
        "query":                api_result.get("query", query),
        "collection":           api_result.get("collection", QDRANT_COLLECTION),
        "category_filter":      api_result.get("category_filter"),
        "stats":                {
            "passed": api_result.get("initial_count", len(initial_chunk_records)),
            "rejected_below_threshold": api_result.get("below_threshold_count", 0),
        },
        "initial_total_chunks": len(initial_chunk_records),
        "initial_top_score":    initial_chunk_records[0]["score"] if initial_chunk_records else 0.0,
        "initial_score_range":  score_range_from_records(initial_chunk_records),
        "total_chunks":         len(chunk_records),
        "reranker_requested":   bool(api_result.get("reranker_requested")),
        "reranker_status":      "reranked" if reranked else api_result.get("reranker_status", "unknown"),
        "reranker_top_k":       reranker_top_k,
        "rerank_error":         api_result.get("rerank_error"),
        "reranked":             reranked,
        "top_score":            round(float(api_result.get("top_score") or 0.0), 5),
        "score_range":          score_range_from_records(chunk_records),
        "embed_ms":             0.0,
        "latency_ms":           round(float(api_result.get("latency_ms") or 0.0), 1),
        "initial_chunks":       initial_chunk_records,
        "reranked_chunks":      reranked_chunk_records,
        "chunks":               chunk_records,
        "via_api":              True,
        "api_url":              endpoint,
    }


def run_single_query(
    query: str,
    top_k: int,
    threshold: float,
    use_reranker: bool,
    reranker_top_k: int,
    category_filter: list[str] | None,
) -> dict:
    """Embed once, search QDRANT_COLLECTION with optional category filter."""
    t0 = time.perf_counter()

    query_vector = embed_query(query)
    embed_ms     = (time.perf_counter() - t0) * 1000

    try:
        chunks, below_count = search_collection(
            query_vector=query_vector,
            collection=QDRANT_COLLECTION,
            top_k=top_k,
            score_threshold=threshold,
            category_filter=category_filter,
        )
        collection_stats = {
            "passed":                   len(chunks),
            "rejected_below_threshold": below_count,
        }
    except (ValueError, Exception) as exc:
        chunks           = []
        collection_stats = {"error": str(exc)}

    # Sort by vector score descending.
    initial_chunks = list(chunks)
    initial_chunks.sort(key=lambda c: c.score, reverse=True)
    initial_chunk_records = chunk_records_from_chunks(initial_chunks)

    # Optionally rerank.
    reranked        = False
    reranker_status = "not_requested"
    rerank_error    = None
    reranked_chunks = []
    output_chunks   = initial_chunks

    if use_reranker:
        if not RERANKER_ENABLED:
            reranker_status = "disabled_by_env"
        elif not initial_chunks:
            reranker_status = "no_chunks"
        else:
            reranker_status = "requested"

    if use_reranker and RERANKER_ENABLED and initial_chunks:
        try:
            from ai.retrieval.reranker import rerank_chunks

            reranked_chunks = rerank_chunks(query, initial_chunks, top_k=reranker_top_k)
            rerank_scores_attached = any(
                getattr(c, "rerank_score", None) is not None
                for c in reranked_chunks
            )
            returned_rerank_top_k = (
                len(reranked_chunks) > 0
                and len(reranked_chunks) <= reranker_top_k
                and len(reranked_chunks) < len(initial_chunks)
            )
            reranked = rerank_scores_attached or returned_rerank_top_k
            if reranked:
                output_chunks = reranked_chunks
                reranker_status = "reranked"
            else:
                reranker_status = "model_unavailable_or_failed_open"
        except Exception as exc:
            rerank_error = str(exc)
            reranker_status = "failed"
            logger.warning("Reranker failed (falling back to vector order): %s", exc)

    latency_ms = (time.perf_counter() - t0) * 1000

    reranked_chunk_records = chunk_records_from_chunks(reranked_chunks) if reranked else []
    chunk_records = reranked_chunk_records if reranked else initial_chunk_records
    output_score_chunks = sorted(output_chunks, key=lambda c: c.score, reverse=True)

    return {
        "query":           query,
        "collection":      QDRANT_COLLECTION,
        "category_filter": category_filter,
        "stats":           collection_stats,
        "initial_total_chunks": len(initial_chunks),
        "initial_top_score":    round(initial_chunks[0].score, 5) if initial_chunks else 0.0,
        "initial_score_range":  score_range(initial_chunks),
        "total_chunks":    len(output_chunks),
        "reranker_requested":   use_reranker,
        "reranker_status":      reranker_status,
        "reranker_top_k":       reranker_top_k,
        "rerank_error":         rerank_error,
        "reranked":        reranked,
        "top_score":       round(output_chunks[0].score, 5) if output_chunks else 0.0,
        "score_range":     score_range(output_score_chunks),
        "embed_ms":   round(embed_ms, 1),
        "latency_ms": round(latency_ms, 1),
        "initial_chunks": initial_chunk_records,
        "reranked_chunks": reranked_chunk_records,
        "chunks":     chunk_records,
    }


def print_chunk_records(chunks: list[dict]) -> None:
    """Print chunk records in the compact debug format."""
    for c in chunks:
        rerank_tag = f"  rerank={c['rerank_score']}" if c["rerank_score"] is not None else ""
        print(
            f"  #{c['rank']:>2}  score={c['score']:.4f}{rerank_tag}  "
            f"cat={c['category']}  {c['source_filename']}  "
            f"heading=\"{c['section_heading'][:50]}\"  "
            f"idx={c['chunk_index']}  len={c['char_len']}"
        )
        print(f"       {c['text_preview'][:200]}...")
        print()


def print_summary(result: dict, idx: int, total: int) -> None:
    """Print a human-readable summary for one query."""
    print(f"\n{SEP}")
    print(f"  Query {idx}/{total}: {result['query']}")
    print(SEP)
    print(f"  Collection       : {result['collection']}")
    print(f"  Category filter  : {result['category_filter'] or '(none - full corpus)'}")
    print(f"  Chunks returned  : {result['total_chunks']}")
    print(f"  Initial chunks   : {result['initial_total_chunks']}")
    print(f"  Top score        : {result['top_score']}")
    print(f"  Score range      : {result['score_range']}")
    print(f"  Reranker status  : {result['reranker_status']}")
    print(f"  Embed latency    : {result['embed_ms']:.0f} ms")
    print(f"  Total latency    : {result['latency_ms']:.0f} ms")

    s = result["stats"]
    if "error" in s:
        print(f"  ERROR: {s['error']}")
    else:
        print(f"  Passed={s['passed']}  rejected={s['rejected_below_threshold']}")

    if result["reranker_requested"]:
        print(THIN)
        print(f"  INITIAL VECTOR CANDIDATES ({len(result['initial_chunks'])})")
        print(THIN)
        print_chunk_records(result["initial_chunks"])

        print(THIN)
        if result["reranked"]:
            print(f"  RERANKER OUTPUT (TOP {len(result['reranked_chunks'])})")
            print(THIN)
            print_chunk_records(result["reranked_chunks"])
        else:
            print(f"  RERANKER OUTPUT: {result['reranker_status']}")
            if result["rerank_error"]:
                print(f"  ERROR: {result['rerank_error']}")
    else:
        print(THIN)
        print_chunk_records(result["chunks"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG retrieval debug - query -> chunk inspection",
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to text file with one query per line, or a literal single query",
    )
    parser.add_argument(
        "--env-file", default=None,
        help=(
            "Optional env file to load before config imports "
            "(default: auto-detect project .env, then ai_server/.env)"
        ),
    )
    parser.add_argument(
        "--category", "-c", nargs="*", default=None,
        help="Filter by one or more categories (e.g. --category sop legal). "
             "Omit to search the full corpus.",
    )
    parser.add_argument(
        "--top-k", "-k", type=int, default=None,
        help=(
            f"Number of chunks to retrieve (default: {RETRIEVAL_TOP_K_PRE_RERANK}; "
            f"{DEBUG_RERANKER_PRE_K} with --reranker)"
        ),
    )
    parser.add_argument(
        "--threshold", "-t", type=float, default=None,
        help=f"Minimum cosine similarity score (default: {RETRIEVAL_SCORE_THRESHOLD})",
    )
    parser.add_argument(
        "--no-rerank", action="store_true",
        help="Skip reranker (default behavior; kept for backward compatibility)",
    )
    parser.add_argument(
        "--reranker", "--rerank", dest="reranker", action="store_true",
        help=(
            "Show both pre-rerank vector candidates and post-rerank results "
            "if RERANKER_ENABLED=true in env"
        ),
    )
    parser.add_argument(
        "--via-api", action="store_true",
        help=(
            "Call the running FastAPI /api/qa/retrieve-debug endpoint instead "
            "of loading retrieval/reranker in this script process"
        ),
    )
    parser.add_argument(
        "--api-url", default=os.getenv("AI_SERVICE_URL", "http://localhost:8000"),
        help="FastAPI base URL for --via-api (default: %(default)s)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output JSON path (default: auto-generated in ai_server/debug_output/)",
    )

    args = parser.parse_args()
    use_reranker = args.reranker and not args.no_rerank

    queries, input_mode = load_queries(args.input)
    if not queries:
        print("ERROR: No queries found in --input.")
        sys.exit(1)

    top_k     = args.top_k or (DEBUG_RERANKER_PRE_K if use_reranker else RETRIEVAL_TOP_K_PRE_RERANK)
    threshold = args.threshold if args.threshold is not None else RETRIEVAL_SCORE_THRESHOLD
    reranker_top_k = RETRIEVAL_TOP_K_POST_RERANK

    category_filter: list[str] | None = None
    if args.category:
        category_filter = [c.strip().lower() for c in args.category if c.strip()]
        if not category_filter:
            category_filter = None

    print(SEP)
    print("  RAG Retrieval Debug Tool")
    print(SEP)
    print(f"  Input                : {args.input}")
    print(f"  Input mode           : {input_mode}")
    print(f"  Env file             : {LOADED_ENV_FILE or '(none found; using process env/defaults)'}")
    print(f"  Queries              : {len(queries)}")
    print(f"  Collection           : {QDRANT_COLLECTION}")
    print(f"  Category filter      : {category_filter or '(none - full corpus)'}")
    print(f"  top_k                : {top_k}")
    print(f"  reranker_top_k       : {reranker_top_k}")
    print(f"  score_threshold      : {threshold}")
    print(f"  via_api              : {args.via_api}")
    if args.via_api:
        print(f"  api_url              : {retrieve_debug_endpoint_url(args.api_url)}")
    print(f"  reranker_enabled     : {RERANKER_ENABLED}")
    print(f"  using reranker       : {use_reranker and RERANKER_ENABLED}")
    print(f"  embedding_backend    : {EMBEDDING_BACKEND}")
    print(f"  qdrant_url           : {QDRANT_URL}")
    print(f"  chunk_size (global)  : {CHUNK_SIZE}")
    print(f"  chunk_overlap (global): {CHUNK_OVERLAP}")
    print(f"  category_chunking    : {USE_CATEGORY_CHUNKING}")
    if USE_CATEGORY_CHUNKING:
        for cat, cfg in CATEGORY_CHUNK_CONFIG.items():
            print(f"    {cat:>12s} -> size={cfg['size']}  overlap={cfg['overlap']}")
    print(SEP)

    results     = []
    total_start = time.perf_counter()

    for i, query in enumerate(queries, 1):
        if args.via_api:
            result = run_single_query_via_api(
                query,
                args.api_url,
                top_k,
                threshold,
                use_reranker,
                reranker_top_k,
                category_filter,
            )
        else:
            result = run_single_query(query, top_k, threshold, use_reranker, reranker_top_k, category_filter)
        results.append(result)
        print_summary(result, i, len(queries))

    total_ms = (time.perf_counter() - total_start) * 1000

    total_chunks       = sum(r["total_chunks"] for r in results)
    total_initial_chunks = sum(r["initial_total_chunks"] for r in results)
    zero_chunk_queries = [r["query"] for r in results if r["total_chunks"] == 0]
    low_score_queries  = [
        r["query"] for r in results
        if r["total_chunks"] > 0 and r["top_score"] < 0.60
    ]
    scores_flat = [c["score"] for r in results for c in r["chunks"]]

    print(f"\n{SEP}")
    print("  AGGREGATE SUMMARY")
    print(SEP)
    print(f"  Total queries        : {len(queries)}")
    if use_reranker:
        print(f"  Initial chunks       : {total_initial_chunks}")
    print(f"  Total chunks returned: {total_chunks}")
    print(f"  Avg chunks/query     : {total_chunks / len(queries):.1f}")
    print(f"  Total time           : {total_ms:.0f} ms")
    print(f"  Avg time/query       : {total_ms / len(queries):.0f} ms")
    if scores_flat:
        print(
            f"  Score min/avg/max    : "
            f"{min(scores_flat):.4f} / {sum(scores_flat)/len(scores_flat):.4f} / {max(scores_flat):.4f}"
        )

    if zero_chunk_queries:
        print(f"\n  ZERO-CHUNK QUERIES ({len(zero_chunk_queries)}):")
        for q in zero_chunk_queries:
            print(f"    - {q}")

    if low_score_queries:
        print(f"\n  LOW TOP-SCORE QUERIES (top_score < 0.60) ({len(low_score_queries)}):")
        for q in low_score_queries:
            print(f"    - {q}")

    print()

    output_dir = AI_SERVER_ROOT / "debug_output"
    output_dir.mkdir(exist_ok=True)

    if args.output:
        out_path = Path(args.output)
    else:
        ts       = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = output_dir / f"retrieval_debug_{ts}.json"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "input":                str(args.input),
            "input_mode":           input_mode,
            "env_file":             str(LOADED_ENV_FILE) if LOADED_ENV_FILE else None,
            "collection":           QDRANT_COLLECTION,
            "category_filter":      category_filter,
            "top_k":                top_k,
            "reranker_top_k":       reranker_top_k,
            "score_threshold":      threshold,
            "via_api":              args.via_api,
            "api_url":              retrieve_debug_endpoint_url(args.api_url) if args.via_api else None,
            "reranker_requested":   use_reranker,
            "reranker_used":        use_reranker and RERANKER_ENABLED,
            "embedding_backend":    EMBEDDING_BACKEND,
            "chunk_size_global":    CHUNK_SIZE,
            "chunk_overlap_global": CHUNK_OVERLAP,
            "category_chunking":    USE_CATEGORY_CHUNKING,
            "category_configs":     CATEGORY_CHUNK_CONFIG if USE_CATEGORY_CHUNKING else {},
        },
        "summary": {
            "total_queries":        len(queries),
            "total_initial_chunks": total_initial_chunks,
            "total_chunks":         total_chunks,
            "avg_chunks_per_query": round(total_chunks / len(queries), 1),
            "total_ms":             round(total_ms, 1),
            "zero_chunk_queries":   zero_chunk_queries,
            "low_score_queries":    low_score_queries,
            "score_min": round(min(scores_flat), 5) if scores_flat else None,
            "score_avg": round(sum(scores_flat) / len(scores_flat), 5) if scores_flat else None,
            "score_max": round(max(scores_flat), 5) if scores_flat else None,
        },
        "results": results,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  JSON report saved -> {out_path}")
    print(SEP)


if __name__ == "__main__":
    main()
