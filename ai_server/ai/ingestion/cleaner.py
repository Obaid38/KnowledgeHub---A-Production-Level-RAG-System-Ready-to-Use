import logging
import re
from dataclasses import dataclass, field

from ai.config.company_profile import load_company_profile

logger = logging.getLogger("knowledge_hub.cleaner")

_PROFILE = load_company_profile()

# Domain entity lists are loaded from shared config so the repo stays generic.
KNOWN_CARRIERS = list(_PROFILE.domain.cleaner_known_carriers)
KNOWN_CUSTOMERS = list(_PROFILE.domain.cleaner_known_customers)

# Regex patterns
_RE_PAGE_NUMBER = re.compile(
    r"^\s*(-\s*)?\d+(\s*-)?\s*$"
    r"|^\s*[Pp]age\s+\d+(\s+of\s+\d+)?\s*$"
)
_RE_HEADING = re.compile(
    r"^(\d+\.[\d.]*\s+.{3,}|[A-Z][A-Z\s]{5,}|#{1,3}\s+.{3,})$"
)
_RE_MONETARY = re.compile(
    r"\$[\d,]+|\bUSD\s*[\d,]+|\b[\d,]+\s*dollars?\b",
    re.IGNORECASE,
)
_RE_TIMELINE = re.compile(
    r"\b(within\s+\d+\s+days?|immediately|ASAP|as\s+soon\s+as\s+possible"
    r"|same\s+day|next\s+day|deadline|due\s+by|no\s+later\s+than"
    r"|Q[1-4]\s*\d{4}|Q[1-4]"
    r"|\b(January|February|March|April|May|June|July|August|September|October|November|December)\b"
    r"|\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b"
    r"|\b(20\d{2})\b"
    r"|schedule|timeline|milestone|by\s+end\s+of)\b",
    re.IGNORECASE,
)
_RE_BLANK_3PLUS = re.compile(r"\n{3,}")


@dataclass
class CleanResult:
    text: str
    headings: list[str] = field(default_factory=list)
    carriers_detected: list[str] = field(default_factory=list)
    customers_detected: list[str] = field(default_factory=list)
    has_monetary_data: bool = False
    has_timeline_data: bool = False


def clean_and_parse(raw_text: str) -> CleanResult:
    lines = raw_text.splitlines()
    cleaned_lines: list[str] = []
    headings: list[str] = []
    has_monetary = False
    has_timeline = False

    for line in lines:
        stripped = line.strip()

        # Skip page number lines
        if stripped and _RE_PAGE_NUMBER.match(stripped):
            continue

        # Detect headings (on non-empty lines)
        if stripped and _RE_HEADING.match(stripped):
            if stripped not in headings:
                headings.append(stripped)

        # Detect signals
        if not has_monetary and _RE_MONETARY.search(stripped):
            has_monetary = True
        if not has_timeline and _RE_TIMELINE.search(stripped):
            has_timeline = True

        cleaned_lines.append(stripped)

    # Join and collapse 3+ consecutive blank lines to 2
    joined = "\n".join(cleaned_lines)
    cleaned_text = _RE_BLANK_3PLUS.sub("\n\n", joined).strip()

    # Entity detection (case-insensitive, deduplicated, order preserved)
    carriers = list(
        dict.fromkeys(
            c for c in KNOWN_CARRIERS if c.lower() in cleaned_text.lower()
        )
    )
    customers = list(
        dict.fromkeys(
            c for c in KNOWN_CUSTOMERS if c.lower() in cleaned_text.lower()
        )
    )

    logger.info(
        "[Cleaner] %d headings, %d carriers, %d customers, monetary=%s, timeline=%s",
        len(headings),
        len(carriers),
        len(customers),
        has_monetary,
        has_timeline,
    )

    return CleanResult(
        text=cleaned_text,
        headings=headings,
        carriers_detected=carriers,
        customers_detected=customers,
        has_monetary_data=has_monetary,
        has_timeline_data=has_timeline,
    )
