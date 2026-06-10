"""Tests for dashboard station display labels."""

from __future__ import annotations

from dashboard.queries import station_label


def test_station_label_prefers_display_name() -> None:
    assert station_label({"name": "wbap-am-820", "display_name": "WBAP 820 AM — Dallas–Fort Worth, TX"}) == (
        "WBAP 820 AM — Dallas–Fort Worth, TX"
    )


def test_station_label_falls_back_to_yaml() -> None:
    assert station_label({"name": "wbap-am-820"}) == "WBAP 820 AM — Dallas–Fort Worth, TX"


def test_station_label_falls_back_to_slug() -> None:
    assert station_label({"name": "unknown-fm"}) == "unknown-fm"
