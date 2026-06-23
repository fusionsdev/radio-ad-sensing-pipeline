"""Self-healing harness — inspect Docker state; restart only with explicit flag."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from tools.harness.lib.common import CheckResult, HarnessResult, PROJECT_ROOT

COMPOSE_FILES = [
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docker-compose.windows-dev.yml",
]


def _compose_ps() -> tuple[list[dict[str, Any]], str | None]:
    argv = ["docker", "compose"]
    for name in COMPOSE_FILES:
        path = PROJECT_ROOT / name
        if path.exists():
            argv.extend(["-f", str(path)])
    argv.extend(["ps", "--format", "json"])
    try:
        completed = subprocess.run(
            argv,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        return [], "docker CLI not found"
    except subprocess.TimeoutExpired:
        return [], "docker compose ps timed out"

    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        return [], err or f"exit {completed.returncode}"

    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows, None


def _restart_service(service: str) -> tuple[bool, str]:
    argv = ["docker", "compose"]
    for name in COMPOSE_FILES:
        path = PROJECT_ROOT / name
        if path.exists():
            argv.extend(["-f", str(path)])
    argv.extend(["restart", service])
    try:
        completed = subprocess.run(
            argv,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    ok = completed.returncode == 0
    detail = (completed.stderr or completed.stdout or "").strip()
    return ok, detail


def run(*, execute_self_heal: bool = False) -> HarnessResult:
    checks: list[CheckResult] = []
    metrics: dict[str, Any] = {
        "execute_self_heal": execute_self_heal,
        "unhealthy_count": 0,
        "exited_count": 0,
    }

    rows, err = _compose_ps()
    if err:
        checks.append(
            CheckResult(
                name="docker_available",
                passed=False,
                detail=err,
                recommended_action="Start Docker Desktop or skip self-healing when offline",
            )
        )
        return HarnessResult(harness="self_healing", passed=False, checks=checks, metrics=metrics)

    checks.append(CheckResult(name="docker_available", passed=True, detail=f"{len(rows)} services reported"))

    unhealthy: list[str] = []
    exited: list[str] = []
    for row in rows:
        name = row.get("Service") or row.get("Name") or "unknown"
        state = (row.get("State") or row.get("Status") or "").lower()
        health = (row.get("Health") or "").lower()
        if "unhealthy" in health or "unhealthy" in state:
            unhealthy.append(name)
        if state.startswith("exited") or "exited" in state:
            exited.append(name)

    metrics["unhealthy_count"] = len(unhealthy)
    metrics["exited_count"] = len(exited)
    metrics["unhealthy_services"] = unhealthy
    metrics["exited_services"] = exited

    checks.append(
        CheckResult(
            name="no_unhealthy_containers",
            passed=len(unhealthy) == 0,
            detail="none" if not unhealthy else ", ".join(unhealthy),
            recommended_action=None
            if not unhealthy
            else "Inspect logs: docker compose logs <service>",
        )
    )
    checks.append(
        CheckResult(
            name="no_exited_containers",
            passed=len(exited) == 0,
            detail="none" if not exited else ", ".join(exited),
            recommended_action=None
            if not exited
            else "Investigate exit reason; restart only with --execute-self-heal",
        )
    )

    if execute_self_heal and (unhealthy or exited):
        targets = sorted(set(unhealthy + exited))
        restarted: list[str] = []
        failed: list[str] = []
        for service in targets:
            ok, detail = _restart_service(service)
            if ok:
                restarted.append(service)
            else:
                failed.append(f"{service}: {detail}")
        metrics["restarted"] = restarted
        metrics["restart_failed"] = failed
        checks.append(
            CheckResult(
                name="execute_self_heal",
                passed=len(failed) == 0,
                detail=f"restarted={restarted}; failed={failed}",
                recommended_action=None if not failed else "Manual docker compose restart required",
            )
        )
    elif unhealthy or exited:
        checks.append(
            CheckResult(
                name="restart_deferred",
                passed=True,
                detail="recommendations recorded; no automatic restart (default)",
            )
        )

    passed = all(c.passed for c in checks)
    return HarnessResult(harness="self_healing", passed=passed, checks=checks, metrics=metrics)