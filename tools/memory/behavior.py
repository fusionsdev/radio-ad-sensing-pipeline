"""Behavior fingerprint registry for decision regression detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.memory._common import (
    BASELINES_DIR,
    BEHAVIOR_COMPONENTS,
    DECISIONS_DIR,
    component_fingerprint,
    ensure_dir,
    utc_now_iso,
)


REGISTRY_PATH = BASELINES_DIR / "behavior_registry.json"


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"components": {}, "updated_at": None}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(registry: dict[str, Any]) -> None:
    ensure_dir(BASELINES_DIR)
    registry["updated_at"] = utc_now_iso()
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def current_fingerprints() -> dict[str, str]:
    return {
        name: component_fingerprint(files)
        for name, files in BEHAVIOR_COMPONENTS.items()
    }


def ensure_baseline(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Initialize missing component baselines from current file hashes."""
    reg = registry if registry is not None else load_registry()
    components = reg.setdefault("components", {})
    now = utc_now_iso()
    for name, fingerprint in current_fingerprints().items():
        if name not in components:
            components[name] = {
                "fingerprint": fingerprint,
                "recorded_at": now,
                "files": BEHAVIOR_COMPONENTS[name],
            }
    save_registry(reg)
    return reg


def changed_components(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return components whose fingerprint differs from baseline."""
    reg = ensure_baseline(registry)
    current = current_fingerprints()
    changes: list[dict[str, Any]] = []
    for name, fingerprint in current.items():
        baseline = reg["components"].get(name, {})
        if baseline.get("fingerprint") != fingerprint:
            changes.append(
                {
                    "component": name,
                    "current_fingerprint": fingerprint,
                    "baseline_fingerprint": baseline.get("fingerprint"),
                    "recorded_at": baseline.get("recorded_at"),
                    "files": BEHAVIOR_COMPONENTS[name],
                }
            )
    return changes


def _decision_covers_change(decision_path: Path, change: dict[str, Any]) -> bool:
    """True if decision file documents the behavioral change."""
    text = decision_path.read_text(encoding="utf-8").lower()
    component = change["component"]
    keywords = {
        "classifier": ("classifier", "loan_classifier", "loan detection", "loan pattern"),
        "station_policy": ("station", "rotation", "stations.yaml", "keep", "watch", "rotate"),
        "dashboard_routing": ("dashboard", "routing", "api/", "router"),
    }
    if any(kw in text for kw in keywords.get(component, ())):
        return True
    for rel in change["files"]:
        if rel.lower() in text or Path(rel).name.lower() in text:
            return True
    return False


def find_covering_decisions(changes: list[dict[str, Any]]) -> dict[str, list[Path]]:
    """Map component name to decision files that document the change."""
    if not DECISIONS_DIR.exists():
        return {}
    decisions = sorted(DECISIONS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    coverage: dict[str, list[Path]] = {c["component"]: [] for c in changes}
    for change in changes:
        recorded_at = change.get("recorded_at") or ""
        for path in decisions:
            if recorded_at:
                # Decision must be newer than baseline record (rough: filename date or mtime)
                pass
            if _decision_covers_change(path, change):
                coverage[change["component"]].append(path)
    return coverage


def undocumented_changes(changes: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return changes with no matching decision file."""
    pending = changes if changes is not None else changed_components()
    if not pending:
        return []
    coverage = find_covering_decisions(pending)
    undocumented: list[dict[str, Any]] = []
    for change in pending:
        if not coverage.get(change["component"]):
            undocumented.append(change)
    return undocumented


def sync_baseline_after_documented_changes(changes: list[dict[str, Any]] | None = None) -> None:
    """Update baseline fingerprints for documented changes."""
    pending = changes if changes is not None else changed_components()
    if not pending:
        return
    coverage = find_covering_decisions(pending)
    reg = load_registry()
    now = utc_now_iso()
    for change in pending:
        if coverage.get(change["component"]):
            reg["components"][change["component"]] = {
                "fingerprint": change["current_fingerprint"],
                "recorded_at": now,
                "files": change["files"],
            }
    save_registry(reg)