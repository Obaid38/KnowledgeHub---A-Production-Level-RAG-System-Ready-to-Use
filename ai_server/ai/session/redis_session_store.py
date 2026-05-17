"""
Redis session store for generic multi-turn conversation persistence.

NODE INTEGRATION NOTE
─────────────────────────────────────────────────────────────────────────────
The Node.js AI service (likely ai.service.js or similar in the Node backend)
currently sends to Python /api/qa/ask:
  { query: string, collection_filter?: string }

ONE LINE CHANGE REQUIRED in that file:
  { query: string, collection_filter?: string, session_id: string }

The session_id value must be the MongoDB conversation/chat document _id
cast to string — the same ID that uniquely identifies the chat thread in
the frontend UI. It is stable for the lifetime of one conversation and
unique per user chat.

No other Node.js changes are required for session persistence to work.
─────────────────────────────────────────────────────────────────────────────
"""
import json
import logging
from typing import Optional

from ai.agents.models.session import SessionContext

logger = logging.getLogger(__name__)

# Load from agents.yml via config loader; fall back to safe defaults if unavailable.
def _load_store_config() -> tuple[int, str]:
    """Return (ttl_seconds, key_prefix) from agents.yml session_store section."""
    try:
        from ai.agents.config.agent_config_loader import load_agents_config
        cfg = load_agents_config().session_store
        return cfg.ttl_seconds, cfg.key_prefix
    except Exception:
        return 3600, "session:v1:"


_TTL_SECONDS, _KEY_PREFIX = _load_store_config()


def _make_key(session_id: str) -> str:
    """
    Build the Redis key for a session.
    Prefix includes schema version so old sessions auto-expire on schema change.
    Increment "v1" to "v2" in agents.yml if the Turn schema changes breaking
    backward compatibility.
    """
    return f"{_KEY_PREFIX}{session_id}"


def load_session(session_id: Optional[str], redis_client) -> SessionContext:
    """
    Load a SessionContext from Redis by session_id.

    Returns a fresh empty SessionContext on:
      - session_id is None (anonymous/smoke-test calls)
      - Redis key miss (new session or TTL expired)
      - Any Redis or deserialization error

    NEVER raises. A Redis failure must never break the pipeline.
    """
    if not session_id:
        return SessionContext()

    try:
        raw = redis_client.get(_make_key(session_id))
        if raw is None:
            logger.debug("Session miss: %s", session_id)
            return SessionContext(session_id=session_id)

        data = json.loads(raw)
        session = SessionContext.from_dict(data)
        logger.debug(
            "Session loaded: %s | turns=%d | window=%d",
            session_id,
            session.turn_count,
            len(session.history_window),
        )
        return session

    except Exception as exc:
        logger.warning(
            "Session load failed for %s: %s. Returning fresh SessionContext.",
            session_id,
            exc,
        )
        return SessionContext(session_id=session_id)


def save_session(
    session_id: Optional[str],
    session: SessionContext,
    redis_client,
) -> None:
    """
    Persist a SessionContext to Redis with TTL.

    No-op if session_id is None.
    NEVER raises. A Redis failure logs a warning and continues silently.
    Called as a FastAPI BackgroundTask — must not add latency to the response.
    """
    if not session_id:
        return

    try:
        data = json.dumps(session.to_dict())
        redis_client.setex(_make_key(session_id), _TTL_SECONDS, data)
        logger.debug(
            "Session saved: %s | turns=%d | ttl=%ds | size=%d bytes",
            session_id,
            session.turn_count,
            _TTL_SECONDS,
            len(data),
        )
    except Exception as exc:
        logger.warning(
            "Session save failed for %s: %s. "
            "Follow-up context will not be available for next turn.",
            session_id,
            exc,
        )
