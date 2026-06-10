"""Tests for CFPB company name normalization."""

from __future__ import annotations

from collectors.normalizers.company_name_normalizer import extract_dba_aliases, normalize_company_name


def test_normalize_strips_inc_suffix() -> None:
    assert normalize_company_name("ENOVA INTERNATIONAL, INC.") == "enova international"


def test_normalize_preserves_brand_token() -> None:
    assert normalize_company_name("CASHNETUSA") == "cashnetusa"


def test_normalize_llc() -> None:
    assert normalize_company_name("National Debt Relief LLC") == "national debt relief"


def test_normalize_bank() -> None:
    assert normalize_company_name("SYNCHRONY BANK") == "synchrony bank"


def test_extract_dba_from_company_field() -> None:
    aliases = extract_dba_aliases("ABC Holdings LLC dba QuickCash")
    assert any("quickcash" in a.lower() for a in aliases)


def test_extract_parenthetical_alias() -> None:
    aliases = extract_dba_aliases("Lender Corp (FastLoan)")
    assert "FastLoan" in aliases
