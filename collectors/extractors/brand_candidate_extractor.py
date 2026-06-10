"""Conservative brand candidate extraction from CFPB complaint fields."""

from __future__ import annotations

import re
from dataclasses import dataclass

from collectors.normalizers.company_name_normalizer import extract_dba_aliases, normalize_company_name

GENERIC_REJECT = frozenset(
    {
        "loan",
        "debt",
        "credit",
        "bank",
        "company",
        "account",
        "payment",
        "collection agency",
        "lender",
        "creditor",
        "servicer",
        "customer service",
        "credit report",
        "the company",
        "my bank",
        "this company",
    }
)

_DOMAIN_PATTERN = re.compile(
    r"\b([a-z0-9][a-z0-9\-]{0,62}\.(?:com|net|org|io|co|us|info))\b",
    re.IGNORECASE,
)
_NARRATIVE_TRIGGERS = (
    (re.compile(r"\bi applied with\s+([A-Z][A-Za-z0-9&'\-\s]{2,40})", re.I), "possible_brand"),
    (re.compile(r"\bi used\s+([A-Z][A-Za-z0-9&'\-\s]{2,40})", re.I), "possible_brand"),
    (re.compile(r"\bi contacted\s+([A-Z][A-Za-z0-9&'\-\s]{2,40})", re.I), "possible_brand"),
    (re.compile(r"\bthe company\s+([A-Z][A-Za-z0-9&'\-\s]{2,40})", re.I), "possible_brand"),
    (re.compile(r"\bloan through\s+([A-Z][A-Za-z0-9&'\-\s]{2,40})", re.I), "lender"),
    (re.compile(r"\baccount with\s+([A-Z][A-Za-z0-9&'\-\s]{2,40})", re.I), "possible_brand"),
)


@dataclass(frozen=True)
class BrandCandidate:
    candidate_name: str
    normalized_candidate: str
    candidate_type: str
    evidence_text: str | None = None


def _is_generic(name: str) -> bool:
    normalized = normalize_company_name(name)
    if not normalized or len(normalized) < 2:
        return True
    if normalized in GENERIC_REJECT:
        return True
    words = normalized.split()
    if len(words) == 1 and words[0] in GENERIC_REJECT:
        return True
    return False


def _classify_company_field(company: str) -> str:
    lower = company.lower()
    if "dba" in lower or "d/b/a" in lower:
        return "dba"
    if "collection" in lower:
        return "collection_agency"
    if any(s in lower for s in (" llc", " inc", " corp", " l.p.", " llp")):
        return "legal_entity"
    if "bank" in lower:
        return "lender"
    if "servic" in lower:
        return "servicer"
    return "company_name"


def extract_from_company(company: str) -> list[BrandCandidate]:
    """Extract candidates from the CFPB company field."""
    if not company or not company.strip():
        return []
    results: list[BrandCandidate] = []
    ctype = _classify_company_field(company)
    normalized = normalize_company_name(company)
    if normalized and not _is_generic(company):
        results.append(
            BrandCandidate(
                candidate_name=company.strip(),
                normalized_candidate=normalized,
                candidate_type=ctype,
                evidence_text=company.strip(),
            )
        )
    for alias in extract_dba_aliases(company):
        norm = normalize_company_name(alias)
        if norm and not _is_generic(alias):
            results.append(
                BrandCandidate(
                    candidate_name=alias.strip(),
                    normalized_candidate=norm,
                    candidate_type="dba",
                    evidence_text=company.strip(),
                )
            )
    return results


def extract_from_narrative(narrative: str) -> list[BrandCandidate]:
    """Extract conservative brand/domain mentions from consumer narrative."""
    if not narrative or not narrative.strip():
        return []
    results: list[BrandCandidate] = []
    seen: set[str] = set()

    for domain_match in _DOMAIN_PATTERN.finditer(narrative):
        domain = domain_match.group(1).lower()
        if domain not in seen:
            seen.add(domain)
            results.append(
                BrandCandidate(
                    candidate_name=domain,
                    normalized_candidate=domain,
                    candidate_type="domain",
                    evidence_text=narrative[:200],
                )
            )

    for pattern, ctype in _NARRATIVE_TRIGGERS:
        for match in pattern.finditer(narrative):
            phrase = match.group(1).strip(" .,\"'")
            norm = normalize_company_name(phrase)
            if not norm or _is_generic(phrase) or norm in seen:
                continue
            seen.add(norm)
            results.append(
                BrandCandidate(
                    candidate_name=phrase,
                    normalized_candidate=norm,
                    candidate_type=ctype,
                    evidence_text=match.group(0)[:120],
                )
            )
    return results
