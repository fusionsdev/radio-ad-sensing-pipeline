"""Server-side Hermes client — local Hermes CLI or host HTTP bridge."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

MAX_HERMES_PROMPT_CHARS = 60_000
LOCAL_PROVIDER = "local_hermes"
LOCAL_MODEL = "hermes-local"
UNAVAILABLE_ERROR = "Local Hermes is not configured or unavailable"

HERMES_SYSTEM_PREFIX = (
    "You are Hermes, an operations assistant for RadioSense, a radio ad detection "
    "and keyword intelligence pipeline.\n"
    "Give concise, prioritized, practical actions.\n"
    "Do not invent data.\n"
    "If evidence is missing, say what is missing.\n"
    "Use the supplied report/context as source of truth.\n\n"
)


def _now_iso() -> str:
    return (
        datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"
    )


def _hermes_timeout_seconds() -> float:
    try:
        return max(5.0, float(os.getenv("HERMES_TIMEOUT_SECONDS", "60")))
    except ValueError:
        return 60.0


def _provider_mode() -> str:
    return os.getenv("HERMES_PROVIDER", "local").strip().lower() or "local"


def _resolve_transport() -> str:
    mode = _provider_mode()
    if mode in {"disabled", "off", "none"}:
        return "disabled"
    if mode in {"local", "local_cli", "cli"}:
        return "local_cli"
    if mode in {"local_http", "http"}:
        return "local_http"
    # Legacy Gemini values are no longer supported.
    if mode == "gemini":
        logger.warning("HERMES_PROVIDER=gemini is deprecated; use local_cli or local_http")
    return "disabled"


def _failure(
    *,
    error: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "provider": LOCAL_PROVIDER,
        "model": LOCAL_MODEL,
        "answer": "",
        "error": error,
        "created_at": created_at or _now_iso(),
    }


def _success(*, answer: str, created_at: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "provider": LOCAL_PROVIDER,
        "model": LOCAL_MODEL,
        "answer": answer,
        "created_at": created_at or _now_iso(),
    }


def _hermes_command() -> list[str]:
    raw = os.getenv("HERMES_COMMAND", "hermes").strip() or "hermes"
    return raw.split()


def _hermes_cli_args() -> list[str]:
    raw = os.getenv("HERMES_CLI_ARGS", "--yolo --accept-hooks --ignore-rules").strip()
    return raw.split() if raw else []


def _prepare_prompt(prompt: str) -> str:
    if prompt.lstrip().startswith("# Hermes Command:"):
        return prompt
    return f"{HERMES_SYSTEM_PREFIX}{prompt}"


def _extract_cli_error(result: subprocess.CompletedProcess[str]) -> str:
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    for line in stderr.splitlines():
        if line.strip():
            return line.strip()
    for line in stdout.splitlines():
        if line.strip().lower().startswith("error:"):
            return line.strip()
    return stderr or stdout or "Local Hermes command failed"


def call_local_hermes_cli(prompt: str, *, timeout_seconds: float) -> str:
    """Invoke local Hermes CLI one-shot mode."""
    command = _hermes_command()
    executable = command[0]
    if not shutil.which(executable):
        raise FileNotFoundError(f"Hermes command not found: {executable}")

    full_prompt = _prepare_prompt(prompt)
    args = [
        *command,
        "-z",
        full_prompt,
        *_hermes_cli_args(),
    ]
    result = subprocess.run(
        args,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(_extract_cli_error(result))
    answer = (result.stdout or "").strip()
    if not answer:
        raise ValueError("Local Hermes returned empty answer")
    return answer


def call_local_hermes_http(prompt: str, *, timeout_seconds: float) -> str:
    """Call a host-side Hermes bridge over HTTP."""
    base_url = os.getenv("HERMES_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise ValueError("HERMES_BASE_URL is not configured")

    url = f"{base_url}/analyze"
    body = json.dumps({"prompt": _prepare_prompt(prompt)}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Local Hermes bridge returned invalid JSON")
    if not payload.get("ok"):
        error = payload.get("error")
        if isinstance(error, str) and error.strip():
            raise RuntimeError(error.strip())
        raise RuntimeError("Local Hermes bridge request failed")
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Local Hermes bridge returned empty answer")
    return answer.strip()


def analyze_prompt(
    command: str,
    prompt: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze an operator prompt via local Hermes."""
    _ = context  # reserved for future routing / audit metadata
    transport = _resolve_transport()
    created_at = _now_iso()
    timeout_seconds = _hermes_timeout_seconds()

    logger.info("Hermes analyze request command=%s transport=%s", command, transport)

    if transport == "disabled":
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)

    if len(prompt) > MAX_HERMES_PROMPT_CHARS:
        return _failure(error="Prompt too large", created_at=created_at)

    try:
        if transport == "local_http":
            answer = call_local_hermes_http(prompt, timeout_seconds=timeout_seconds)
        else:
            answer = call_local_hermes_cli(prompt, timeout_seconds=timeout_seconds)
        return _success(answer=answer, created_at=created_at)
    except FileNotFoundError:
        logger.warning("Hermes CLI missing command=%s", command)
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)
    except subprocess.TimeoutExpired:
        logger.warning("Hermes timeout command=%s transport=%s", command, transport)
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)
    except urllib.error.HTTPError as exc:
        logger.warning(
            "Hermes HTTP error command=%s status=%s",
            command,
            exc.code,
        )
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)
    except urllib.error.URLError:
        logger.warning("Hermes HTTP unreachable command=%s transport=%s", command, transport)
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)
    except TimeoutError:
        logger.warning("Hermes timeout command=%s transport=%s", command, transport)
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)
    except (RuntimeError, ValueError) as exc:
        logger.warning("Hermes call failed command=%s detail=%s", command, exc)
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)
    except Exception:
        logger.exception("Hermes unexpected error command=%s", command)
        return _failure(error=UNAVAILABLE_ERROR, created_at=created_at)