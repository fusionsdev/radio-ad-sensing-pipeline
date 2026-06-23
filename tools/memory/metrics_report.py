"""Generate Memory OS analytics reports (Latest.md / Latest.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.memory.metrics_collector import (
    METRICS_ROOT,
    collect_snapshot,
    ensure_metrics_dirs,
    latest_metrics_age_days,
    write_daily_snapshot,
)

LATEST_JSON = METRICS_ROOT / "Latest.json"
LATEST_MD = METRICS_ROOT / "Latest.md"
FRESHNESS_DAYS = 7


def build_analytics_payload(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Structured payload for dashboard and harness consumers."""
    snap = snapshot or collect_snapshot().to_dict()
    memory = snap.get("memory", {})
    growth = snap.get("growth", {})
    harness = snap.get("harness", {})
    headroom = snap.get("headroom", {})
    agents = snap.get("agents", {})

    return {
        "collected_at": snap.get("collected_at"),
        "date": snap.get("date"),
        "memory_health": snap.get("memory_health", "unknown").upper(),
        "memory_growth": {
            "decisions": memory.get("total_decisions", 0),
            "incidents": memory.get("total_incidents", 0),
            "stations": memory.get("total_station_changes", 0),
            "runbooks": memory.get("total_runbooks", 0),
            "memory_files": memory.get("total_memory_files", 0),
        },
        "growth_7d": {
            "decisions": growth.get("new_decisions_7d", 0),
            "incidents": growth.get("new_incidents_7d", 0),
            "station_updates": growth.get("new_station_updates_7d", 0),
            "vault_files": growth.get("vault_growth_7d", 0),
        },
        "growth_30d": {
            "vault_files": growth.get("vault_growth_30d", 0),
        },
        "harness_statistics": {
            "runs": harness.get("harness_runs", 0),
            "passes": harness.get("harness_passes", 0),
            "failures": harness.get("harness_failures", 0),
            "pass_rate_pct": harness.get("pass_rate_pct", 0.0),
            "last_status": harness.get("last_status", "unknown"),
            "last_timestamp": harness.get("last_timestamp"),
        },
        "headroom_statistics": {
            "reachable": headroom.get("proxy_reachable", False),
            "healthy": headroom.get("proxy_healthy", False),
            "status": headroom.get("headroom_status", "unknown"),
            "enabled_sessions": headroom.get("enabled_sessions", 0),
            "recent_runs": headroom.get("recent_runs", 0),
        },
        "agent_sessions": {
            "codex": agents.get("codex_sessions", 0),
            "cursor": agents.get("cursor_sessions", 0),
            "claude": agents.get("claude_sessions", 0),
            "grok": agents.get("grok_sessions", 0),
            "hermes": agents.get("hermes_sessions", 0),
            "source": agents.get("source", "best_effort_markers"),
        },
        "degraded": False,
    }


def format_latest_markdown(payload: dict[str, Any]) -> str:
    mg = payload.get("memory_growth", {})
    g7 = payload.get("growth_7d", {})
    hs = payload.get("harness_statistics", {})
    hr = payload.get("headroom_statistics", {})

    reachable = "YES" if hr.get("reachable") else "NO"
    lines = [
        "# Memory OS Analytics",
        "",
        f"**Collected:** {payload.get('collected_at', '—')}",
        f"**Memory Health:** {payload.get('memory_health', 'UNKNOWN')}",
        "",
        "## Totals",
        "",
        f"- Decisions: {mg.get('decisions', 0)}",
        f"- Incidents: {mg.get('incidents', 0)}",
        f"- Station changes: {mg.get('stations', 0)}",
        f"- Runbooks: {mg.get('runbooks', 0)}",
        f"- Memory files: {mg.get('memory_files', 0)}",
        "",
        "## Growth (7d)",
        "",
        f"- +{g7.get('decisions', 0)} decisions",
        f"- +{g7.get('incidents', 0)} incidents",
        f"- +{g7.get('station_updates', 0)} station updates",
        f"- +{g7.get('vault_files', 0)} vault files",
        "",
        "## Harness",
        "",
        f"- Pass rate: {hs.get('pass_rate_pct', 0)}%",
        f"- Runs: {hs.get('runs', 0)} | Passes: {hs.get('passes', 0)} | Failures: {hs.get('failures', 0)}",
        f"- Last status: {hs.get('last_status', 'unknown')}",
        "",
        "## Headroom",
        "",
        f"- Reachable: {reachable}",
        f"- Status: {hr.get('status', 'unknown')}",
        f"- Recent runs (7d): {hr.get('recent_runs', 0)}",
        "",
    ]
    return "\n".join(lines)


def generate_report(*, write_daily: bool = True) -> dict[str, Any]:
    """Collect metrics, write daily snapshot, and refresh Latest.* files."""
    ensure_metrics_dirs()
    snapshot = collect_snapshot()
    if write_daily:
        write_daily_snapshot(snapshot)
    payload = build_analytics_payload(snapshot.to_dict())
    LATEST_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    LATEST_MD.write_text(format_latest_markdown(payload) + "\n", encoding="utf-8")
    return payload


def metrics_freshness_status() -> dict[str, Any]:
    age = latest_metrics_age_days()
    if age is None:
        return {"passed": False, "status": "fail", "detail": "Latest.json missing", "age_days": None}
    stale = age > FRESHNESS_DAYS
    return {
        "passed": not stale,
        "status": "warning" if stale else "pass",
        "detail": f"age={age:.1f}d (threshold {FRESHNESS_DAYS}d)",
        "age_days": round(age, 2),
    }


def format_observability_section(metrics: dict[str, Any]) -> list[str]:
    status = str(metrics.get("observability_status", "unknown")).upper()
    freshness = "PASS" if metrics.get("metrics_fresh") else "WARNING"
    report = "PASS" if metrics.get("analytics_report_ok") else "FAIL"
    return [
        "## Observability Status",
        "",
        f"**Observability:** {status}",
        f"**Metrics Freshness:** {freshness}",
        f"**Analytics Report:** {report}",
        "",
    ]