import logging
import re
from dataclasses import dataclass, field

from ai.ingestion.cleaner import KNOWN_CARRIERS, KNOWN_CUSTOMERS

logger = logging.getLogger("knowledge_hub.signals")

# --- Compiled regex patterns (module-level, deterministic) ---

_RE_MONETARY = re.compile(
    r"\$[\d,]+|\bUSD\s*[\d,]+|\b[\d,]+\s*dollars?\b",
    re.IGNORECASE,
)

_RE_DATES = re.compile(
    r"\b(Q[1-4]\s*\d{4}|Q[1-4]"
    r"|January|February|March|April|May|June|July|August"
    r"|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    r"|20\d{2})\b",
    re.IGNORECASE,
)

_RE_DEADLINES = re.compile(
    r"\b(deadline|due\s+by|no\s+later\s+than|by\s+end\s+of"
    r"|ASAP|as\s+soon\s+as\s+possible|immediately"
    r"|within\s+\d+\s+days?|same\s+day|next\s+day)\b",
    re.IGNORECASE,
)

# Numbered steps: "Step 1", "1.", "1)", at line start
_RE_STEPS = re.compile(
    r"^\s*(step\s+\d+|[1-9]\d?\.|[1-9]\d?\))\s+\S",
    re.IGNORECASE | re.MULTILINE,
)

# Email or phone number
_RE_CONTACT = re.compile(
    r"[\w.+\-]+@[\w\-]+\.\w+"
    r"|\+?1?[\s.\-]?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}",
    re.IGNORECASE,
)

# Job-role keywords
_RE_ROLES = re.compile(
    r"\b(manager|director|coordinator|analyst|supervisor"
    r"|representative|officer|specialist|executive|lead|head\s+of)\b",
    re.IGNORECASE,
)

# Combined entity list for entity_mentions detection
_ALL_ENTITIES: list[str] = KNOWN_CARRIERS + KNOWN_CUSTOMERS


@dataclass
class ChunkSignals:
    has_monetary_figures: bool = False
    has_dates: bool = False
    has_deadlines: bool = False
    has_steps: bool = False
    has_contact_info: bool = False
    has_roles: bool = False
    entity_mentions: list[str] = field(default_factory=list)
    # Filled by the integration layer (smoke script / Celery task), not by extract_signals():
    has_table_data: bool = False
    table_name: str | None = None


def extract_signals(chunk_text: str) -> ChunkSignals:
    """Extract structured signals from a single chunk of text.

    Returns a ChunkSignals dataclass.  has_table_data and table_name are left
    at their defaults (False / None) — the caller sets them when the chunk is
    known to be a table chunk.
    """
    text_lower = chunk_text.lower()

    has_monetary = bool(_RE_MONETARY.search(chunk_text))
    has_dates = bool(_RE_DATES.search(chunk_text))
    has_deadlines = bool(_RE_DEADLINES.search(chunk_text))
    has_steps = bool(_RE_STEPS.search(chunk_text))
    has_contact = bool(_RE_CONTACT.search(chunk_text))
    has_roles = bool(_RE_ROLES.search(chunk_text))

    entity_mentions = list(
        dict.fromkeys(
            e for e in _ALL_ENTITIES if e.lower() in text_lower
        )
    )

    signals = ChunkSignals(
        has_monetary_figures=has_monetary,
        has_dates=has_dates,
        has_deadlines=has_deadlines,
        has_steps=has_steps,
        has_contact_info=has_contact,
        has_roles=has_roles,
        entity_mentions=entity_mentions,
    )

    logger.debug(
        "[Signals] monetary=%s dates=%s deadlines=%s steps=%s contact=%s roles=%s entities=%s",
        has_monetary,
        has_dates,
        has_deadlines,
        has_steps,
        has_contact,
        has_roles,
        entity_mentions,
    )
    return signals
