"""Collect Memory OS observability metrics from read-only vault and harness sources."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tools.harness.lib.common import REPORTS_DIR
from tools.memory._common import (
    DECISIONS_DIR,
    INCIDENTS_DIR,
    MEMORY_ROOT,
    PROJECT_ROOT,
    RUNBOOKS_DIR,
    STATIONS_DIR,
    ensure_dir,
    find_markdown_files,
    today_str,
    utc_now_iso,
)
from tools.memory.analytics import count_harness_report_files, count_station_history_entries, count_vault_growth
from tools.memory.memory_report import build_memory_health
from tools.memory.metrics_models import (
    AgentMetrics,
    GrowthMetrics,
    HarnessMetrics,
    HeadroomMetrics,
    MemoryCounts,
    MetricsSnapshot,
)

METRICS_ROOT = MEMORY_ROOT / "Metrics"
DAILY_DIR = METRICS_ROOT / "Daily"
WEEKLY_DIR = METRICS_ROOT / "Weekly"
MONTHLY_DIR = METRICS_ROOT / "Monthly"
PROJECTMEM_EVENTS = PROJECT_ROOT / ".projectmem" / "events.jsonl"

AGENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "codex": ("codex", "codex.md", "radiosense_task_master"),
    "cursor": ("cursor", "headroom-context", ".cursor"),
    "claude": ("claude", "claude.md", "claude code"),
    "grok": ("grok", "grok.md"),
    "hermes": ("hermes", ".hermes.md", "pipeline-ops", "telegram"),
}

STATION_HISTORY_RE = re.compile(
    r"^\-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*\s+—\s+(\w+):",
    re.MULTILINE,
)


def ensure_metrics_dirs() -> None:
    for path in (METRICS_ROOT, DAILY_DIR, WEEKLY_DIR, MONTHLY_DIR):
        ensure_dir(path)


def _mtime_within_days(path: Path, days: int) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return mtime >= datetime.now(tz=UTC) - timedelta(days=days)


def _count_new_in_dir(directory: Path, days: int) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.glob("*.md") if _mtime_within_days(path, days))


def _count_station_updates_days(days: int) -> int:
    if not STATIONS_DIR.exists():
        return 0
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    total = 0
    for path in STATIONS_DIR.glob("*.md"):
        if path.name.lower() == "batch policy.md":
            continue
        for match in STATION_HISTORY_RE.finditer(path.read_text(encoding="utf-8")):
            try:
                entry_date = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                continue
            if entry_date >= cutoff:
                total += 1
    return total


def _count_memory_files() -> int:
    if not MEMORY_ROOT.exists():
        return 0
    return len(
        [
            p
            for p in find_markdown_files(MEMORY_ROOT)
            if ".obsidian" not in p.parts and ".smart-env" not in p.parts and "Metrics" not in p.parts
        ]
    )


def _load_harness_latest() -> dict[str, Any]:
    json_path = REPORTS_DIR / "latest.json"
    if not json_path.exists():
        return {}
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _harness_metrics_from_snapshots() -> HarnessMetrics:
    snapshots = sorted(DAILY_DIR.glob("*-metrics.json"))
    runs = len(snapshots)
    passes = 0
    failures = 0
    last_status = "unknown"
    last_timestamp: str | None = None

    for path in snapshots:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        status = str(data.get("harness", {}).get("last_status", "")).lower()
        if status == "pass":
            passes += 1
        elif status == "fail":
            failures += 1

    latest = _load_harness_latest()
    if latest:
        runs = max(runs, 1)
        last_status = str(latest.get("status", "unknown"))
        last_timestamp = latest.get("timestamp")
        if last_status == "pass":
            passes = max(passes, 1)
        elif last_status == "fail":
            failures = max(failures, 1)

    pass_rate = round((passes / runs) * 100, 1) if runs else 0.0
    return HarnessMetrics(
        harness_runs=runs,
        harness_passes=passes,
        harness_failures=failures,
        pass_rate_pct=pass_rate,
        last_status=last_status,
        last_timestamp=last_timestamp,
    )


def _headroom_metrics_from_latest() -> HeadroomMetrics:
    latest = _load_harness_latest()
    headroom = latest.get("headroom_status") or {}
    if not headroom:
        harnesses = latest.get("harnesses") or {}
        headroom = (harnesses.get("headroom") or {}).get("metrics") or {}

    reachable = bool(headroom.get("proxy_reachable"))
    healthy = bool(headroom.get("proxy_healthy"))
    status = str(headroom.get("headroom_status", "unknown"))

    enabled_sessions = 0
    recent_runs = 0
    cutoff = datetime.now(tz=UTC) - timedelta(days=7)
    for path in DAILY_DIR.glob("*-metrics.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        collected = data.get("collected_at")
        if collected:
            try:
                ts = datetime.strptime(collected, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            except ValueError:
                ts = None
            if ts and ts >= cutoff:
                recent_runs += 1
        if data.get("headroom", {}).get("proxy_reachable"):
            enabled_sessions += 1

    if reachable:
        enabled_sessions = max(enabled_sessions, 1)

    return HeadroomMetrics(
        proxy_reachable=reachable,
        proxy_healthy=healthy,
        headroom_status=status,
        enabled_sessions=enabled_sessions,
        recent_runs=recent_runs,
    )


def _agent_metrics_best_effort() -> AgentMetrics:
    counts = {key: 0 for key in AGENT_KEYWORDS}
    blobs: list[str] = []

    if PROJECTMEM_EVENTS.exists():
        for line in PROJECTMEM_EVENTS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            blobs.append(line.lower())
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = " ".join(
                str(event.get(k, ""))
                for k in ("summary", "notes", "type")
            ).lower()
            for agent, keywords in AGENT_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    counts[agent] += 1

    if DECISIONS_DIR.exists():
        for path in DECISIONS_DIR.glob("*.md"):
            text = path.read_text(encoding="utf-8").lower()
            blobs.append(text)
            for agent, keywords in AGENT_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    counts[agent] += 1

    marker_files = {
        "codex": PROJECT_ROOT / "CODEX.md",
        "cursor": PROJECT_ROOT / ".cursor" / "rules" / "headroom-context.mdc",
        "claude": PROJECT_ROOT / "CLAUDE.md",
        "grok": PROJECT_ROOT / "GROK.md",
        "hermes": PROJECT_ROOT / ".hermes.md",
    }
    for agent, path in marker_files.items():
        if path.exists() and _mtime_within_days(path, 7):
            counts[agent] += 1

    return AgentMetrics(
        codex_sessions=counts["codex"],
        cursor_sessions=counts["cursor"],
        claude_sessions=counts["claude"],
        grok_sessions=counts["grok"],
        hermes_sessions=counts["hermes"],
    )


def collect_snapshot(date: str | None = None) -> MetricsSnapshot:
    """Build a metrics snapshot from read-only sources."""
    ensure_metrics_dirs()
    snapshot_date = date or today_str()
    health = build_memory_health() if MEMORY_ROOT.exists() else {"status": "fail"}

    memory = MemoryCounts(
        total_decisions=len(list(DECISIONS_DIR.glob("*.md"))) if DECISIONS_DIR.exists() else 0,
        total_incidents=len(list(INCIDENTS_DIR.glob("*.md"))) if INCIDENTS_DIR.exists() else 0,
        total_station_changes=count_station_history_entries(),
        total_runbooks=len(list(RUNBOOKS_DIR.glob("*.md"))) if RUNBOOKS_DIR.exists() else 0,
        total_memory_files=_count_memory_files(),
    )
    growth = GrowthMetrics(
        new_decisions_7d=_count_new_in_dir(DECISIONS_DIR, 7),
        new_incidents_7d=_count_new_in_dir(INCIDENTS_DIR, 7),
        new_station_updates_7d=_count_station_updates_days(7),
        vault_growth_7d=count_vault_growth(7),
        vault_growth_30d=count_vault_growth(30),
    )

    return MetricsSnapshot(
        date=snapshot_date,
        collected_at=utc_now_iso(),
        memory_health="pass" if health.get("status") == "pass" else "fail",
        memory=memory,
        growth=growth,
        agents=_agent_metrics_best_effort(),
        harness=_harness_metrics_from_snapshots(),
        headroom=_headroom_metrics_from_latest(),
    )


def write_daily_snapshot(snapshot: MetricsSnapshot | None = None) -> Path:
    """Write YYYY-MM-DD-metrics.json under project-memory/Metrics/Daily/."""
    ensure_metrics_dirs()
    snap = snapshot or collect_snapshot()
    path = DAILY_DIR / f"{snap.date}-metrics.json"
    path.write_text(json.dumps(snap.to_dict(), indent=2) + "\n", encoding="utf-8")
    _rollup_period( WEEKLY_DIR, 7)
    _rollup_period(MONTHLY_DIR, 30)
    return path


def _rollup_period(target_dir: Path, days: int) -> None:
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    snapshots: list[dict[str, Any]] = []
    for path in sorted(DAILY_DIR.glob("*-metrics.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        collected = data.get("collected_at")
        if not collected:
            continue
        try:
            ts = datetime.strptime(collected, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            continue
        if ts >= cutoff:
            snapshots.append(data)

    if not snapshots:
        return

    label = f"{days}d"
    rollup = {
        "period": label,
        "collected_at": utc_now_iso(),
        "snapshot_count": len(snapshots),
        "memory": snapshots[-1].get("memory", {}),
        "growth": {
            "vault_growth_period": sum(s.get("growth", {}).get("vault_growth_7d", 0) for s in snapshots),
            "new_decisions_period": sum(s.get("growth", {}).get("new_decisions_7d", 0) for s in snapshots),
            "new_incidents_period": sum(s.get("growth", {}).get("new_incidents_7d", 0) for s in snapshots),
        },
        "harness": {
            "runs": len(snapshots),
            "pass_rate_pct": round(
                sum(1 for s in snapshots if s.get("harness", {}).get("last_status") == "pass")
                / len(snapshots)
                * 100,
                1,
            ),
        },
        "headroom": {
            "reachable_runs": sum(1 for s in snapshots if s.get("headroom", {}).get("proxy_reachable")),
        },
    }
    stamp = today_str()
    out = target_dir / f"{stamp}-{label}-rollup.json"
    out.write_text(json.dumps(rollup, indent=2) + "\n", encoding="utf-8")


def latest_metrics_age_days() -> float | None:
    path = METRICS_ROOT / "Latest.json"
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return (datetime.now(tz=UTC) - mtime).total_seconds() / 86400