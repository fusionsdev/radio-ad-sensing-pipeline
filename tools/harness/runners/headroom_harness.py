"""Headroom harness — verify context compression layer (Phase 1.9)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

from tools.harness.lib.common import PROJECT_ROOT, CheckResult, HarnessResult

HEADROOM_CONFIG_DIR = PROJECT_ROOT / "config" / "headroom"
REQUIRED_CONFIG_FILES = (
    "README.md",
    "headroom-settings.md",
    "agent-routing.md",
    "integration-status.md",
)
HEADROOM_HOST = "127.0.0.1"
HEADROOM_PORT = 8787
HEADROOM_PROXY_URL = f"http://{HEADROOM_HOST}:{HEADROOM_PORT}"
HEADROOM_HEALTH_URL = f"{HEADROOM_PROXY_URL}/health"
HEADROOM_CONNECT_TIMEOUT_S = 2.0

AGENT_SHIMS = {
    "codex": PROJECT_ROOT / "CODEX.md",
    "claude": PROJECT_ROOT / "CLAUDE.md",
    "grok": PROJECT_ROOT / "GROK.md",
}
CURSOR_HEADROOM_RULE = PROJECT_ROOT / ".cursor" / "rules" / "headroom-context.mdc"
LOAD_ORDER_FILE = PROJECT_ROOT / "project-memory" / "04_Agent_Load_Order.md"


def _port_reachable(host: str, port: int, timeout: float = HEADROOM_CONNECT_TIMEOUT_S) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _health_check(url: str = HEADROOM_HEALTH_URL, timeout: float = HEADROOM_CONNECT_TIMEOUT_S) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            if response.status != 200:
                return False, f"HTTP {response.status}"
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return False, "invalid JSON response"
            status = str(payload.get("status", "")).lower()
            if status == "healthy":
                return True, "healthy"
            return False, f"status={payload.get('status', 'unknown')}"
    except urllib.error.URLError as exc:
        return False, str(exc.reason)
    except TimeoutError:
        return False, "timeout"
    except OSError as exc:
        return False, str(exc)


def _file_contains(path: Path, needles: list[str]) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, [f"missing file: {path.name}"]
    text = path.read_text(encoding="utf-8").lower()
    missing = [n for n in needles if n.lower() not in text]
    return len(missing) == 0, missing


def _overall_status(*, config_ok: bool, agent_ok: bool, proxy_ok: bool, health_ok: bool) -> str:
    if not config_ok or not agent_ok:
        return "fail"
    if not proxy_ok or not health_ok:
        return "warning"
    return "pass"


def format_headroom_status_section(metrics: dict) -> list[str]:
    status = str(metrics.get("headroom_status", "unknown")).upper()
    proxy = "PASS" if metrics.get("proxy_reachable") else "WARNING"
    health = "PASS" if metrics.get("proxy_healthy") else "WARNING"
    agents = "PASS" if metrics.get("agent_files_ok") else "FAIL"
    config = "PASS" if metrics.get("config_ok") else "FAIL"
    return [
        "## Headroom Status",
        "",
        f"**Headroom:** {status}",
        f"**Proxy Reachable:** {proxy}",
        f"**Health:** {health}",
        f"**Agent Files:** {agents}",
        f"**Config:** {config}",
        "",
    ]


def run() -> HarnessResult:
    checks: list[CheckResult] = []

    config_dir_ok = HEADROOM_CONFIG_DIR.is_dir()
    checks.append(
        CheckResult(
            name="config_dir",
            passed=config_dir_ok,
            detail=str(HEADROOM_CONFIG_DIR) if config_dir_ok else "config/headroom/ missing",
            recommended_action=None if config_dir_ok else "Create config/headroom/ per Phase 1.9 spec",
        )
    )

    missing_config = [
        name for name in REQUIRED_CONFIG_FILES if not (HEADROOM_CONFIG_DIR / name).exists()
    ]
    config_files_ok = config_dir_ok and not missing_config
    checks.append(
        CheckResult(
            name="config_files",
            passed=config_files_ok,
            detail="all present" if config_files_ok else f"missing: {', '.join(missing_config)}",
            recommended_action=None if config_files_ok else "Add required files under config/headroom/",
        )
    )

    missing_shims = [name for name, path in AGENT_SHIMS.items() if not path.exists()]
    agent_files_ok = len(missing_shims) == 0
    checks.append(
        CheckResult(
            name="agent_files",
            passed=agent_files_ok,
            detail="ok" if agent_files_ok else f"missing: {', '.join(missing_shims)}",
            recommended_action=None if agent_files_ok else "Create CODEX.md, CLAUDE.md, GROK.md",
        )
    )

    shim_headroom_ok = True
    shim_issues: list[str] = []
    for name, path in AGENT_SHIMS.items():
        if not path.exists():
            continue
        ok, missing = _file_contains(
            path,
            ["agents.md", "04_agent_load_order", "headroom", "tools/harness/run_all.py"],
        )
        if not ok:
            shim_headroom_ok = False
            shim_issues.append(f"{name}: {missing}")
    checks.append(
        CheckResult(
            name="agent_shims_headroom",
            passed=shim_headroom_ok,
            detail="ok" if shim_headroom_ok else f"missing refs: {shim_issues}",
            recommended_action=None if shim_headroom_ok else "Add Headroom + load order to agent shims",
        )
    )

    cursor_ok, cursor_missing = _file_contains(
        CURSOR_HEADROOM_RULE,
        ["agents.md", "04_agent_load_order", "8787"],
    ) if CURSOR_HEADROOM_RULE.exists() else (False, ["headroom-context.mdc"])
    checks.append(
        CheckResult(
            name="cursor_headroom_rule",
            passed=cursor_ok,
            detail="ok" if cursor_ok else f"missing: {cursor_missing}",
            recommended_action=None if cursor_ok else "Create .cursor/rules/headroom-context.mdc",
        )
    )

    proxy_reachable = _port_reachable(HEADROOM_HOST, HEADROOM_PORT)
    checks.append(
        CheckResult(
            name="proxy_port",
            passed=proxy_reachable,
            detail=f"{HEADROOM_HOST}:{HEADROOM_PORT} reachable"
            if proxy_reachable
            else f"{HEADROOM_HOST}:{HEADROOM_PORT} not reachable (optional)",
            recommended_action=None
            if proxy_reachable
            else "Start local proxy: headroom proxy --memory --code-graph",
        )
    )

    health_ok = False
    health_detail = "skipped — port closed"
    if proxy_reachable:
        health_ok, health_detail = _health_check()
    checks.append(
        CheckResult(
            name="proxy_health",
            passed=health_ok,
            detail=health_detail if proxy_reachable else "port unreachable",
            recommended_action=None
            if health_ok
            else "Ensure headroom proxy responds on GET /health",
        )
    )

    config_ok = config_dir_ok and config_files_ok and cursor_ok
    agent_ok = agent_files_ok and shim_headroom_ok
    overall = _overall_status(
        config_ok=config_ok,
        agent_ok=agent_ok,
        proxy_ok=proxy_reachable,
        health_ok=health_ok,
    )

    metrics = {
        "headroom_status": overall,
        "proxy_reachable": proxy_reachable,
        "proxy_healthy": health_ok,
        "config_ok": config_ok,
        "agent_files_ok": agent_ok,
        "proxy_url": HEADROOM_PROXY_URL,
        "load_order_file": str(LOAD_ORDER_FILE.relative_to(PROJECT_ROOT)),
    }

    passed = overall != "fail"
    return HarnessResult(harness="headroom", passed=passed, checks=checks, metrics=metrics)