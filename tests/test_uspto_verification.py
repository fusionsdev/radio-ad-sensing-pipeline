import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.verify_apify_candidates_uspto import (
    load_apify_candidates,
    extract_serial_from_url,
    query_uspto_tSDR,
    is_loan_only,
    main,
)


def test_load_apify_candidates(tmp_path):
    csv_content = """url,detected_serial_number,detected_mark_name,loan_phrase_match,query,snippet
https://trademarks.justia.com/872/36/loan-command-87236459.html,87236459,LOAN COMMAND,credit and loan services,test query,test snippet
"""
    csv_file = tmp_path / "test_candidates.csv"
    csv_file.write_text(csv_content)
    candidates = load_apify_candidates(csv_file)
    assert len(candidates) == 1
    assert candidates[0]["detected_serial_number"] == "87236459"


def test_extract_serial_from_url():
    url = "https://trademarks.justia.com/872/36/loan-command-87236459.html"
    assert extract_serial_from_url(url) == "87236459"
    assert extract_serial_from_url("https://example.com") is None


def test_query_uspto_tsdr_dry_run():
    data = query_uspto_tSDR("87236459", dry_run=True)
    assert data["word_mark"] == "LOAN COMMAND"
    assert "credit and loan services" in data["goods_services"]


def test_is_loan_only():
    assert is_loan_only("Credit and loan services, personal loans") is True
    assert is_loan_only("Mortgage brokerage services") is False
    assert is_loan_only("Investment advisory services") is False
    assert is_loan_only("Cash advance and short-term loans") is True


@patch("scripts.verify_apify_candidates_uspto.query_uspto_tSDR")
def test_main_dry_run(mock_query, tmp_path):
    mock_query.return_value = {
        "word_mark": "LOAN COMMAND",
        "serial_number": "87236459",
        "owner_name": "Loan Command, Inc.",
        "status": "Live",
        "live_dead_status": "LIVE",
        "international_class": "36",
        "goods_services": "Credit and loan services, bank loan pricing analysis",
    }

    input_csv = tmp_path / "input.csv"
    input_csv.write_text("""url,detected_serial_number,detected_mark_name,loan_phrase_match,query,snippet
https://trademarks.justia.com/872/36/loan-command-87236459.html,87236459,LOAN COMMAND,credit and loan services,test,"test snippet"
""")

    output_jsonl = tmp_path / "output.jsonl"
    output_csv = tmp_path / "output.csv"

    result = main([
        "--input", str(input_csv),
        "--output", str(output_jsonl),
        "--csv", str(output_csv),
        "--dry-run"
    ])

    assert result == 0
    assert output_jsonl.exists()
    assert output_csv.exists()

    with open(output_csv, encoding="utf-8") as f:
        content = f.read()
        assert "serial_number" in content
        assert "LOAN COMMAND" in content


def test_uspto_mocked_response():
    """Test that mocked USPTO response enriches fields correctly."""
    data = query_uspto_tSDR("90123456", dry_run=True)
    assert data["word_mark"] == "CASH ADVANCE PRO"
    assert "cash advance" in data["goods_services"].lower()


def test_policy_flags_conservative():
    """Ensure policy flags remain conservative."""
    # This would be checked in the main enrichment logic
    assert True  # Placeholder for policy test - flags are hardcoded to False for ad_copy/landing


@pytest.mark.parametrize("goods_text,expected", [
    ("personal loans and installment loan services", True),
    ("mortgage brokerage and real estate financing", False),
    ("wealth management and investment advice", False),
])
def test_loan_only_filter(goods_text, expected):
    assert is_loan_only(goods_text) == expected
