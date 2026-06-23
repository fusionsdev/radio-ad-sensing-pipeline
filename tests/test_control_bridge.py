"""Tests for the host-side RadioSense control bridge."""

from __future__ import annotations

import importlib.util
import json
import sys
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = REPO_ROOT / "scripts" / "radiosense_control_bridge.py"


def _load_bridge_module():
    spec = importlib.util.spec_from_file_location("radiosense_control_bridge", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bridge_module():
    return _load_bridge_module()


def test_control_bridge_health_endpoint(bridge_module) -> None:
    server = bridge_module.ThreadingHTTPServer(("127.0.0.1", 0), bridge_module.ControlBridgeHandler)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/health")
        response = conn.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert body["ok"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_control_bridge_rejects_unknown_action(bridge_module) -> None:
    server = bridge_module.ThreadingHTTPServer(("127.0.0.1", 0), bridge_module.ControlBridgeHandler)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/action/run-shell")
        response = conn.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        assert response.status == 404
        assert body["ok"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_control_bridge_recheck_action(bridge_module) -> None:
    server = bridge_module.ThreadingHTTPServer(("127.0.0.1", 0), bridge_module.ControlBridgeHandler)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch.object(bridge_module, "_component_status", return_value={"checked_at": "now"}):
            conn = HTTPConnection(host, port, timeout=5)
            conn.request("POST", "/action/recheck")
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert body["action"] == "recheck"
        assert body["next_check_in_seconds"] == 10
    finally:
        server.shutdown()
        server.server_close()