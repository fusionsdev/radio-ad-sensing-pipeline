#!/usr/bin/env python3
"""Host-side allowlisted control bridge for RadioSense operator actions.

Run on the Windows/Linux host (not inside radio-dashboard):

    python scripts/radiosense_control_bridge.py

Docker dashboard proxies actions via:

    http://host.docker.internal:8792
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("radiosense-control-bridge")

HOST = os.getenv("RADIOSENSE_CONTROL_HOST", "127.0.0.1")
PORT = int(os.getenv("RADIOSENSE_CONTROL_PORT", "8792"))
TIMEOUT = float(os.getenv("RADIOSENSE_CONTROL_TIMEOUT_SECONDS", "120"))
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime"
LOG_FILE = RUNTIME_DIR / "radiosense_control_bridge.log"
FRONTEND_DIR = Path(
    os.getenv(
        "RADIOSENSE_FRONTEND_DIR",
        r"H:\DEV\github_sandbox\radiosense-aistudio",
    )
)
FRONTEND_URL = os.getenv("RADIOSENSE_FRONTEND_URL", "http://localhost:5150/")
HERMES_BRIDGE_URL = os.getenv("HERMES_BRIDGE_URL", "http://127.0.0.1:8791")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://127.0.0.1:3000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090")
BACKEND_HEALTH_URL = os.getenv("BACKEND_HEALTH_URL", "http://127.0.0.1:8081/health")
DOCKER_COMPOSE_FILES = [
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docker-compose.windows-dev.yml",
]
DASHBOARD_CONTAINER = "radio-dashboard"
STARTUP_COMMAND = (
    "cd H:\\DEV\\projects\\radio-ad-sensing-pipeline\n"
    ".\\scripts\\start-radiosense-stack.ps1 -OpenBrowser"
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"


def _tail_text(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _log_action(action: str, ok: bool, detail: str = "") -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{_now_iso()} action={action} ok={ok}"
    if detail:
        line += f" detail={detail[:500]}"
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _read_recent_actions(limit: int = 20) -> list[dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    actions: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        actions.append({"line": line})
    return actions


def _http_probe(url: str, timeout: float = 3.0) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "body": _tail_text(body, 500),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status_code": exc.code,
            "body": _tail_text(body, 500),
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _run_subprocess(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    shell: bool = False,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout or TIMEOUT,
            check=False,
            shell=shell,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": _tail_text((result.stdout or "").strip()),
            "stderr": _tail_text((result.stderr or "").strip()),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Command timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _docker_compose_args() -> list[str]:
    args = ["docker", "compose"]
    for compose_file in DOCKER_COMPOSE_FILES:
        args.extend(["-f", compose_file])
    return args


def _docker_dashboard_status() -> dict[str, Any]:
    if not shutil.which("docker"):
        return {"status": "unknown", "detail": "docker not found"}
    result = _run_subprocess(
        ["docker", "inspect", "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", DASHBOARD_CONTAINER],
        timeout=15,
    )
    if not result.get("ok"):
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        if "No such object" in stdout or "No such object" in stderr:
            return {"status": "down", "detail": "container not found"}
        return {"status": "unknown", "detail": result.get("error") or stderr or stdout}
    parts = (result.get("stdout") or "unknown|none").split("|", 1)
    state = parts[0].strip() or "unknown"
    health = parts[1].strip() if len(parts) > 1 else "none"
    if state != "running":
        return {"status": "down", "detail": state, "health": health}
    if health == "healthy":
        return {"status": "healthy", "detail": state, "health": health}
    if health == "unhealthy":
        return {"status": "unhealthy", "detail": state, "health": health}
    return {"status": "running", "detail": state, "health": health}


def _component_status() -> dict[str, Any]:
    hermes = _http_probe(f"{HERMES_BRIDGE_URL.rstrip('/')}/health")
    frontend = _http_probe(FRONTEND_URL)
    backend = _http_probe(BACKEND_HEALTH_URL)
    docker = _docker_dashboard_status()
    return {
        "checked_at": _now_iso(),
        "hermes_bridge": {
            "expected": HERMES_BRIDGE_URL,
            "status": "online" if hermes.get("ok") else "offline",
            "detail": hermes,
        },
        "frontend": {
            "expected": FRONTEND_URL,
            "status": "running" if frontend.get("ok") else "offline",
            "detail": frontend,
        },
        "backend_api": {
            "expected": BACKEND_HEALTH_URL,
            "status": "online" if backend.get("ok") else "offline",
            "detail": backend,
        },
        "docker_dashboard": {
            "expected": DASHBOARD_CONTAINER,
            "status": docker.get("status", "unknown"),
            "detail": docker,
        },
        "control_bridge": {
            "expected": f"http://{HOST}:{PORT}",
            "status": "online",
        },
    }


def action_start_hermes_bridge() -> dict[str, Any]:
    started_at = _now_iso()
    script = REPO_ROOT / "scripts" / "start-hermes-bridge.ps1"
    if sys.platform == "win32":
        result = _run_subprocess(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Background"],
            cwd=REPO_ROOT,
            timeout=60,
        )
    else:
        result = _run_subprocess(["python", "scripts/hermes_bridge.py"], cwd=REPO_ROOT, timeout=5)
    probe = _http_probe(f"{HERMES_BRIDGE_URL.rstrip('/')}/health")
    ok = bool(probe.get("ok"))
    _log_action("start-hermes-bridge", ok)
    return _action_response(
        "start-hermes-bridge",
        started_at=started_at,
        result={"ok": ok, "result": result},
        message="Hermes bridge started" if ok else "Hermes bridge failed to start",
        probe=probe,
    )


def _action_response(
    action: str,
    *,
    started_at: str,
    result: dict[str, Any],
    message: str | None = None,
    ok: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
    finished_at = _now_iso()
    subprocess_result = result.get("result") if isinstance(result.get("result"), dict) else result
    stdout_tail = ""
    stderr_tail = ""
    if isinstance(subprocess_result, dict):
        stdout_tail = str(subprocess_result.get("stdout") or "")
        stderr_tail = str(subprocess_result.get("stderr") or "")
    payload = {
        "ok": bool(ok if ok is not None else result.get("ok")),
        "action": action,
        "started_at": started_at,
        "finished_at": finished_at,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "next_check_in_seconds": 10,
        "message": message or result.get("message"),
        **result,
        **extra,
    }
    return payload


def action_restart_dashboard() -> dict[str, Any]:
    started_at = _now_iso()
    if not shutil.which("docker"):
        payload = {"ok": False, "action": "restart-dashboard", "error": "docker not found"}
        _log_action("restart-dashboard", False, "docker not found")
        return _action_response("restart-dashboard", started_at=started_at, result=payload, ok=False)
    args = [*_docker_compose_args(), "up", "-d", "dashboard"]
    result = _run_subprocess(args, cwd=REPO_ROOT, timeout=180)
    status = _docker_dashboard_status()
    ok = status.get("status") in {"healthy", "running"}
    _log_action("restart-dashboard", ok, status.get("status", "unknown"))
    return _action_response(
        "restart-dashboard",
        started_at=started_at,
        result={"ok": ok, "result": result},
        message="Dashboard container restarted" if ok else "Dashboard restart finished with issues",
        docker_dashboard=status,
    )


def action_start_frontend() -> dict[str, Any]:
    probe = _http_probe(FRONTEND_URL)
    if probe.get("ok"):
        _log_action("start-frontend", True, "already running")
        return {
            "ok": True,
            "action": "start-frontend",
            "message": "Frontend already running",
            "probe": probe,
        }
    if not FRONTEND_DIR.is_dir():
        payload = {
            "ok": False,
            "action": "start-frontend",
            "error": f"Frontend directory not found: {FRONTEND_DIR}",
        }
        _log_action("start-frontend", False, "missing frontend dir")
        return payload
    if sys.platform == "win32":
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"Set-Location '{FRONTEND_DIR}'; npm run dev",
            ],
            cwd=str(FRONTEND_DIR),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    else:
        subprocess.Popen(["npm", "run", "dev"], cwd=str(FRONTEND_DIR))
    import time

    time.sleep(4)
    probe = _http_probe(FRONTEND_URL, timeout=8)
    ok = bool(probe.get("ok"))
    _log_action("start-frontend", ok)
    return {
        "ok": ok,
        "action": "start-frontend",
        "message": "Frontend dev server started" if ok else "Frontend start requested; verify manually",
        "probe": probe,
    }


def _open_url(url: str, action_name: str) -> dict[str, Any]:
    if sys.platform == "win32":
        result = _run_subprocess(["cmd", "/c", "start", "", url], timeout=10)
    elif sys.platform == "darwin":
        result = _run_subprocess(["open", url], timeout=10)
    else:
        result = _run_subprocess(["xdg-open", url], timeout=10)
    ok = bool(result.get("ok"))
    _log_action(action_name, ok, url)
    return {
        "ok": ok,
        "action": action_name,
        "url": url,
        "result": result,
        "message": f"Opened {url}" if ok else f"Failed to open {url}",
    }


def action_open_grafana() -> dict[str, Any]:
    return _open_url(GRAFANA_URL, "open-grafana")


def action_open_prometheus() -> dict[str, Any]:
    return _open_url(PROMETHEUS_URL, "open-prometheus")


def action_open_backend_health() -> dict[str, Any]:
    return _open_url(BACKEND_HEALTH_URL, "open-backend-health")


def action_recheck() -> dict[str, Any]:
    started_at = _now_iso()
    components = _component_status()
    ok = bool((components.get("backend_api") or {}).get("detail", {}).get("ok"))
    _log_action("recheck", ok)
    return _action_response(
        "recheck",
        started_at=started_at,
        result={"ok": True},
        message="Component status refreshed",
        components=components,
    )


def action_open_dashboard_logs() -> dict[str, Any]:
    started_at = _now_iso()
    if not shutil.which("docker"):
        payload = {"ok": False, "error": "docker not found"}
        _log_action("open-dashboard-logs", False, "docker not found")
        return _action_response("open-dashboard-logs", started_at=started_at, result=payload, ok=False)
    result = _run_subprocess(
        ["docker", "logs", DASHBOARD_CONTAINER, "--tail", "200"],
        timeout=30,
    )
    ok = bool(result.get("ok"))
    log_path = RUNTIME_DIR / "radio-dashboard-tail.log"
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        (result.get("stdout") or "") + ("\n" + result.get("stderr") if result.get("stderr") else ""),
        encoding="utf-8",
    )
    if sys.platform == "win32" and ok:
        _run_subprocess(["notepad", str(log_path)], timeout=10)
    _log_action("open-dashboard-logs", ok, str(log_path))
    return _action_response(
        "open-dashboard-logs",
        started_at=started_at,
        result={"ok": ok, "result": result},
        message=f"Dashboard logs saved to {log_path}" if ok else "Failed to read dashboard logs",
        log_path=str(log_path),
    )


def action_test_hermes() -> dict[str, Any]:
    health = _http_probe(f"{HERMES_BRIDGE_URL.rstrip('/')}/health")
    if not health.get("ok"):
        _log_action("test-hermes", False, "bridge offline")
        return {
            "ok": False,
            "action": "test-hermes",
            "error": "Hermes bridge is offline",
            "health": health,
        }
    payload = json.dumps({"prompt": "Reply with exactly: RadioSense Hermes OK"}).encode("utf-8")
    request = urllib.request.Request(
        f"{HERMES_BRIDGE_URL.rstrip('/')}/analyze",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
            ok = bool(body.get("ok"))
            _log_action("test-hermes", ok)
            return {
                "ok": ok,
                "action": "test-hermes",
                "response": body,
                "message": "Local Hermes test passed" if ok else body.get("error", "Hermes test failed"),
            }
    except Exception as exc:  # noqa: BLE001
        _log_action("test-hermes", False, str(exc))
        return {"ok": False, "action": "test-hermes", "error": str(exc), "health": health}


ACTIONS: dict[str, Any] = {
    "start-hermes-bridge": action_start_hermes_bridge,
    "restart-dashboard": action_restart_dashboard,
    "start-frontend": action_start_frontend,
    "open-grafana": action_open_grafana,
    "open-prometheus": action_open_prometheus,
    "open-backend-health": action_open_backend_health,
    "open-dashboard-logs": action_open_dashboard_logs,
    "recheck": action_recheck,
    "test-hermes": action_test_hermes,
}


class ControlBridgeHandler(BaseHTTPRequestHandler):
    server_version = "RadioSenseControlBridge/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "radiosense-control-bridge"})
            return
        if self.path == "/status":
            components = _component_status()
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "radiosense-control-bridge",
                    "startup_command": STARTUP_COMMAND,
                    "components": components,
                    "recent_actions": _read_recent_actions(),
                },
            )
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if not self.path.startswith("/action/"):
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        action_name = self.path.removeprefix("/action/").strip("/")
        handler = ACTIONS.get(action_name)
        if handler is None:
            self._send_json(404, {"ok": False, "error": f"unknown action: {action_name}"})
            return
        result = handler()
        status = 200 if result.get("ok") else 503
        self._send_json(status, result)


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), ControlBridgeHandler)
    logger.info("RadioSense control bridge listening on http://%s:%s", HOST, PORT)
    logger.info("Log file: %s", LOG_FILE)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("RadioSense control bridge stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())