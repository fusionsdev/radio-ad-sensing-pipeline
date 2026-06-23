"""Data models for Memory OS observability metrics (Phase 1.95)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MemoryCounts:
    total_decisions: int = 0
    total_incidents: int = 0
    total_station_changes: int = 0
    total_runbooks: int = 0
    total_memory_files: int = 0


@dataclass
class GrowthMetrics:
    new_decisions_7d: int = 0
    new_incidents_7d: int = 0
    new_station_updates_7d: int = 0
    vault_growth_7d: int = 0
    vault_growth_30d: int = 0


@dataclass
class AgentMetrics:
    codex_sessions: int = 0
    cursor_sessions: int = 0
    claude_sessions: int = 0
    grok_sessions: int = 0
    hermes_sessions: int = 0
    source: str = "best_effort_markers"


@dataclass
class HarnessMetrics:
    harness_runs: int = 0
    harness_passes: int = 0
    harness_failures: int = 0
    pass_rate_pct: float = 0.0
    last_status: str = "unknown"
    last_timestamp: str | None = None


@dataclass
class HeadroomMetrics:
    proxy_reachable: bool = False
    proxy_healthy: bool = False
    headroom_status: str = "unknown"
    enabled_sessions: int = 0
    recent_runs: int = 0


@dataclass
class MetricsSnapshot:
    date: str
    collected_at: str
    memory_health: str = "unknown"
    memory: MemoryCounts = field(default_factory=MemoryCounts)
    growth: GrowthMetrics = field(default_factory=GrowthMetrics)
    agents: AgentMetrics = field(default_factory=AgentMetrics)
    harness: HarnessMetrics = field(default_factory=HarnessMetrics)
    headroom: HeadroomMetrics = field(default_factory=HeadroomMetrics)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)