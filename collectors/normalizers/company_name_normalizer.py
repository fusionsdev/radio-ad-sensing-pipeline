"""Company name normalization for CFPB entity aggregation."""

from __future__ import annotations

import re

LEGAL_SUFFIXES = (
    r"\bincorporated\b",
    r"\binc\.?\b",
    r"\bllc\.?\b",
    r"\bl\.l\.c\.?\b",
    r"\bcorporation\b",
    r"\bcorp\.?\b",
    r"\bco\.?\b",
    r"\bcompany\b",
    r"\bholdings\b",
    r"\bgroup\b",
    r"\blp\.?\b",
    r"\bllp\.?\b",
    r"\bltd\.?\b",
    r"\blimited\b",
    r"\bplc\.?\b",
    r"\bn\.?a\.?\b",
)

_SUFFIX_PATTERN = re.compile(
    r"(?:,\s*)?(?:" + "|".join(LEGAL_SUFFIXES) + r")\.?\s*$",
    re.IGNORECASE,
)
_DBA_PATTERN = re.compile(
    r"(?:dba|d/b/a|doing business as)\s*[:\-]?\s*(.+?)(?:\)|,|$)",
    re.IGNORECASE,
)
_PARENS_PATTERN = re.compile(r"\(([^)]+)\)")


def normalize_company_name(raw: str) -> str:
    """Lowercase, strip legal suffixes and punctuation; preserve distinct tokens."""
    if not raw or not raw.strip():
        return ""
    name = raw.strip().lower()
    name = re.sub(r"[^\w\s&'-]", " ", name)
    prev = None
    while prev != name:
        prev = name
        name = _SUFFIX_PATTERN.sub("", name).strip()
    name = re.sub(r"\s+", " ", name).strip(" ,.-")
    return name


def extract_dba_aliases(raw: str) -> list[str]:
    """Extract DBA and parenthetical alias strings from company field."""
    if not raw:
        return []
    aliases: list[str] = []
    for match in _DBA_PATTERN.finditer(raw):
        alias = match.group(1).strip(" .,\"'")
        if alias and alias.lower() not in {a.lower() for a in aliases}:
            aliases.append(alias)
    for match in _PARENS_PATTERN.finditer(raw):
        inner = match.group(1).strip()
        if inner and not re.match(r"^(inc|llc|corp|ltd)\.?$", inner, re.I):
            if inner.lower() not in {a.lower() for a in aliases}:
                aliases.append(inner)
    return aliases
