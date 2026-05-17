"""
Session dataclasses for multi-turn conversation persistence.

CONFIRMED FIELD NAMES (read before modifying):
  Turn fields (existing):
    query_original, query_reformulated, answer_text, answer_summary,
    chunk_ids, route_used, style_used, timestamp, query_vector
  Turn fields (added in Step 6a):
    citations, chunks, top_score
  Chunk objects from Qdrant (RetrievedChunk):
    chunk_text (text content), source_filename, page_number,
    score, category, extraction_method
  SessionContext.turns — the actual field backing the sliding window
  SessionContext.history_window — property alias for turns
  add_turn() — added here in Step 6a (did not exist before)
  Redis client import: from ai.config import REDIS_URL (used in store, not here)
"""
from dataclasses import dataclass, field
from types import SimpleNamespace


@dataclass
class Turn:
    # ------------------------------------------------------------------
    # Existing fields — names unchanged
    # ------------------------------------------------------------------
    query_original: str
    query_reformulated: str | None
    answer_text: str
    answer_summary: str | None
    chunk_ids: list[str]
    route_used: str
    style_used: str
    timestamp: str               # ISO 8601 string
    query_vector: list[float] | None

    # ------------------------------------------------------------------
    # New fields added in Step 6a
    # ------------------------------------------------------------------
    citations: list[dict] | None = None   # CitationResult.citations as plain dicts
    chunks: list = field(default_factory=list)   # full RetrievedChunk objects
    top_score: float | None = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return all fields as a JSON-serializable plain dict."""
        # query_vector: handle numpy arrays gracefully
        qv = self.query_vector
        if qv is None:
            serialized_vector: list[float] = []
        elif hasattr(qv, "tolist"):
            serialized_vector = qv.tolist()
        else:
            serialized_vector = list(qv) if qv else []

        # chunks: serialize full chunk objects (RetrievedChunk or SimpleNamespace)
        serialized_chunks = []
        for chunk in (self.chunks or []):
            if isinstance(chunk, dict):
                serialized_chunks.append({
                    "text": chunk.get("text") or chunk.get("chunk_text"),
                    "source_filename": chunk.get("source_filename"),
                    "page_number": chunk.get("page_number"),
                    "score": chunk.get("score"),
                    "category": chunk.get("category"),
                    "extraction_method": chunk.get("extraction_method"),
                })
            else:
                # Attribute access — RetrievedChunk uses chunk_text, not text
                serialized_chunks.append({
                    "text": getattr(chunk, "chunk_text", getattr(chunk, "text", None)),
                    "source_filename": getattr(chunk, "source_filename", None),
                    "page_number": getattr(chunk, "page_number", None),
                    "score": getattr(chunk, "score", None),
                    "category": getattr(chunk, "category", None),
                    "extraction_method": getattr(chunk, "extraction_method", None),
                })

        return {
            "query_original": self.query_original,
            "query_reformulated": self.query_reformulated,
            "answer_text": self.answer_text,
            "answer_summary": self.answer_summary,
            "chunk_ids": list(self.chunk_ids),
            "route_used": self.route_used,
            "style_used": self.style_used,
            "timestamp": self.timestamp,
            "query_vector": serialized_vector,
            "citations": self.citations if self.citations else [],
            "chunks": serialized_chunks,
            "top_score": self.top_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Turn":
        """Reconstruct Turn from a plain dict. Never raises on missing keys."""
        # query_vector: always reconstruct as list[float], never numpy
        qv_raw = data.get("query_vector")
        if qv_raw:
            query_vector: list[float] = [float(x) for x in qv_raw]
        else:
            query_vector = []

        # chunks: reconstruct as SimpleNamespace for attribute access
        raw_chunks = data.get("chunks") or []
        chunks = [
            SimpleNamespace(
                text=c.get("text"),
                source_filename=c.get("source_filename"),
                page_number=c.get("page_number"),
                score=c.get("score"),
                category=c.get("category"),
                extraction_method=c.get("extraction_method"),
            )
            for c in raw_chunks
        ]

        return cls(
            query_original=data.get("query_original", ""),
            query_reformulated=data.get("query_reformulated"),
            answer_text=data.get("answer_text", ""),
            answer_summary=data.get("answer_summary"),
            chunk_ids=data.get("chunk_ids") or [],
            route_used=data.get("route_used", ""),
            style_used=data.get("style_used", ""),
            timestamp=data.get("timestamp"),
            query_vector=query_vector,
            citations=data.get("citations") or [],
            chunks=chunks,
            top_score=data.get("top_score"),
        )


@dataclass
class SessionContext:
    session_id: str = ""
    turns: list[Turn] = field(default_factory=list)
    turn_count: int = 0

    # ------------------------------------------------------------------
    # New fast-access stored fields (Step 6a)
    # ------------------------------------------------------------------
    last_reformulated_query: str | None = None
    last_confidence: float | None = None
    last_citations: list[dict] | None = None

    # ------------------------------------------------------------------
    # Derived properties — read from the most recent turn
    # ------------------------------------------------------------------

    @property
    def history_window(self) -> list[Turn]:
        """Alias for turns — the sliding-window view of conversation history."""
        return self.turns

    @property
    def last_query(self) -> str | None:
        return self.turns[-1].query_original if self.turns else None

    @property
    def last_answer(self) -> str | None:
        return self.turns[-1].answer_text if self.turns else None

    @property
    def last_chunks(self):
        """Return the most recent full chunk objects, falling back to chunk_ids."""
        if not self.turns:
            return []
        last = self.turns[-1]
        return last.chunks if last.chunks else last.chunk_ids

    @property
    def last_route(self) -> str | None:
        return self.turns[-1].route_used if self.turns else None

    # ------------------------------------------------------------------
    # add_turn — manages the sliding window and updates fast-access fields
    # ------------------------------------------------------------------

    def add_turn(self, turn: "Turn") -> None:
        """
        Append a completed turn to the session history.
        Enforces max 4-turn sliding window (evicts oldest).
        Updates all fast-access scalar fields.
        """
        max_turns = 4
        try:
            from ai.agents.config.agent_config_loader import load_agents_config
            max_turns = load_agents_config().session_store.max_turns_in_window
        except Exception:
            pass

        self.turns.append(turn)
        if len(self.turns) > max_turns:
            self.turns.pop(0)   # evict oldest

        # Update new fast-access stored fields
        self.last_citations = turn.citations if turn.citations else None

        if turn.query_reformulated:
            self.last_reformulated_query = turn.query_reformulated

        if turn.top_score is not None:
            self.last_confidence = turn.top_score

        self.turn_count += 1

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_chunk(chunk) -> dict:
        if isinstance(chunk, dict):
            return {
                "text": chunk.get("text") or chunk.get("chunk_text"),
                "source_filename": chunk.get("source_filename"),
                "page_number": chunk.get("page_number"),
                "score": chunk.get("score"),
                "category": chunk.get("category"),
                "extraction_method": chunk.get("extraction_method"),
            }
        return {
            "text": getattr(chunk, "chunk_text", getattr(chunk, "text", None)),
            "source_filename": getattr(chunk, "source_filename", None),
            "page_number": getattr(chunk, "page_number", None),
            "score": getattr(chunk, "score", None),
            "category": getattr(chunk, "category", None),
            "extraction_method": getattr(chunk, "extraction_method", None),
        }

    def to_dict(self) -> dict:
        """Serialize all fields as a JSON-serializable plain dict."""
        last_chunks_serialized = [
            self._serialize_chunk(c) for c in (self.last_chunks or [])
        ]
        return {
            "session_id": self.session_id,
            "last_query": self.last_query,
            "last_reformulated_query": self.last_reformulated_query,
            "last_answer": self.last_answer,
            "last_confidence": self.last_confidence,
            "last_citations": self.last_citations,
            "last_chunks": last_chunks_serialized,
            "turn_count": self.turn_count,
            "history_window": [t.to_dict() for t in self.turns],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionContext":
        """Reconstruct SessionContext from a plain dict. Never raises on missing keys."""
        turns = [Turn.from_dict(t) for t in data.get("history_window", [])]

        # last_chunks is derived from turns[-1].chunks via property — no explicit storage needed.
        # last_query and last_answer are derived from turns[-1] via properties.

        return cls(
            session_id=data.get("session_id", ""),
            turns=turns,
            turn_count=data.get("turn_count", 0),
            last_reformulated_query=data.get("last_reformulated_query"),
            last_confidence=data.get("last_confidence"),
            last_citations=data.get("last_citations"),
        )
