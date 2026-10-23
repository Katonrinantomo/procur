"""
Item name matching with rapidfuzz.

normalize_name() lowercases, strips punctuation, and unifies volume units so
"20 liter", "20 ltr" and "20 L" all become "20l".

match_item() scores the normalized query against every catalog item name and
alias and returns the best match above the configured threshold.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Item

# ---------------------------------------------------------------------------
# Unit synonyms → canonical form
# ---------------------------------------------------------------------------
_UNIT_MAP: dict[str, str] = {
    # volume
    "liter": "l",
    "litre": "l",
    "ltr": "l",
    "lt": "l",
    "l": "l",
    # weight
    "kilogram": "kg",
    "kilo": "kg",
    # length
    "meter": "m",
    "metre": "m",
    "mtr": "m",
    # misc
    "pcs": "pcs",
    "buah": "pcs",
    "piece": "pcs",
    "pieces": "pcs",
    "inch": "in",
    "inchi": "in",
}

_UNIT_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(re.escape(k) for k in _UNIT_MAP) + r")\b",
    re.IGNORECASE,
)

_PUNCT = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalize_name(text: str) -> str:
    """
    Normalize an item name for fuzzy matching.

    Steps:
    1. Lowercase.
    2. Replace quantity+unit tokens (e.g. "20 liter" → "20l").
    3. Strip remaining punctuation.
    4. Collapse whitespace.
    """
    text = text.lower()

    def _replace_unit(m: re.Match) -> str:
        number = m.group(1).replace(",", ".")
        unit = _UNIT_MAP[m.group(2).lower()]
        return f"{number}{unit}"

    text = _UNIT_PATTERN.sub(_replace_unit, text)
    text = _PUNCT.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text


def match_item(raw_name: str, session: Session) -> Item | None:
    """
    Return the best-matching catalog Item for *raw_name*, or None if no item
    scores at or above settings.MATCH_THRESHOLD.
    """
    query = normalize_name(raw_name)
    threshold = settings.MATCH_THRESHOLD

    best_item: Item | None = None
    best_score: float = 0.0

    items = session.query(Item).all()
    for item in items:
        candidates = [item.name] + (item.aliases or [])
        for candidate in candidates:
            score = fuzz.token_set_ratio(query, normalize_name(candidate))
            if score > best_score:
                best_score = score
                best_item = item

    if best_score >= threshold:
        return best_item
    return None
