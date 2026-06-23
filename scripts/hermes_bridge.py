#!/usr/bin/env python3
"""Host-side HTTP bridge from Docker dashboard to local Hermes CLI.

Run on the Windows/Linux host (not inside radio-dashboard):

    python scripts/hermes_bridge.py

Docker dashboard should use:

    HERMES_PROVIDER=local_http
    HERMES_BASE_URL=http://host.docker.internal:8791
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("hermes-bridge")

HOST = os.getenv("HERMES_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("HERMES_BRIDGE_PORT", "8791"))
TIMEOUT = float(os.getenv("HERMES_TIMEOUT_SECONDS", "120"))
COMMAND = os.getenv("HERMES_COMMAND", "hermes -p radio-runner")
CLI_ARGS = os.getenv("HERMES_CLI_ARGS", "--yolo --accept-hooks --ignore-rules")
HERMES_PROFILE = os.getenv("HERMES_PROFILE", "radio-runner").strip()
HERMES_CWD = os.getenv(
    "HERMES_CWD",
    str(Path(__file__).resolve().parents[1]),
).strip()


def _command_parts() -> list[str]:
    return COMMAND.strip().split()


def _cli_args() -> list[str]:
    return CLI_ARGS.strip().split() if CLI_ARGS.strip() else []


def _extract_error(result: subprocess.CompletedProcess[str]) -> str:
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    for line in stderr.splitlines():
        if line.strip():
            return line.strip()
    for line in stdout.splitlines():
        if line.strip().lower().startswith("error:"):
            return line.strip()
    return stderr or stdout or "Local Hermes command failed"


def run_local_hermes(prompt: str) -> dict[str, Any]:
    command = _command_parts()
    executable = command[0]
    if not shutil.which(executable):
        return {
            "ok": False,
            "provider": "local_hermes",
            "answer": "",
            "error": f"Hermes command not found: {executable}",
        }

    args = [*command, "-z", prompt, *_cli_args()]
    env = os.environ.copy()
    if HERMES_PROFILE:
        env["HERMES_PROFILE"] = HERMES_PROFILE
    cwd = HERMES_CWD if HERMES_CWD and Path(HERMES_CWD).is_dir() else None
    try:
        result = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=TIMEOUT,
            check=False,
            shell=False,
            env=env,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "provider": "local_hermes",
            "answer": "",
            "error": "Local Hermes timed out",
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "provider": "local_hermes",
            "answer": "",
            "error": _extract_error(result),
        }

    answer = (result.stdout or "").strip()
    if not answer:
        return {
            "ok": False,
            "provider": "local_hermes",
            "answer": "",
            "error": "Local Hermes returned empty answer",
        }

    return {
        "ok": True,
        "provider": "local_hermes",
        "model": "hermes-local",
        "answer": answer,
    }


class HermesBridgeHandler(BaseHTTPRequestHandler):
    server_version = "HermesBridge/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "hermes-bridge"})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/analyze":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return

        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            self._send_json(400, {"ok": False, "error": "prompt is required"})
            return

        result = run_local_hermes(prompt.strip())
        status = 200 if result.get("ok") else 503
        self._send_json(status, result)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), HermesBridgeHandler)
    logger.info("Hermes bridge listening on http://%s:%s", HOST, PORT)
    logger.info("Hermes command: %s", COMMAND)
    logger.info("Hermes profile: %s", HERMES_PROFILE or "(default)")
    logger.info("Hermes cwd: %s", HERMES_CWD)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Hermes bridge stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())