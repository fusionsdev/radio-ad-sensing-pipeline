"""Small nvidia-smi based Prometheus exporter for Windows Docker Desktop.

Native dcgm-exporter needs Linux PCI/DCGM access that is not available in the
Windows dev overlay. This exporter keeps the existing DCGM metric names used by
Grafana while sourcing values from nvidia-smi inside an NVIDIA-enabled container.
"""

from __future__ import annotations

import html
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable

QUERY_FIELDS = (
    "name",
    "memory.used",
    "memory.total",
    "utilization.gpu",
    "temperature.gpu",
)


def _parse_float(value: str) -> float:
    value = value.strip()
    if value in {"", "[Not Supported]", "N/A"}:
        return 0.0
    return float(value)


def parse_nvidia_smi_csv(lines: Iterable[str]) -> list[dict[str, float | str]]:
    gpus: list[dict[str, float | str]] = []
    for index, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != len(QUERY_FIELDS):
            raise ValueError(f"expected {len(QUERY_FIELDS)} columns, got {len(parts)}: {line!r}")
        name, memory_used, memory_total, gpu_util, temperature = parts
        gpus.append(
            {
                "gpu": str(index),
                "name": name,
                "memory_used_mib": _parse_float(memory_used),
                "memory_total_mib": _parse_float(memory_total),
                "gpu_util_percent": _parse_float(gpu_util),
                "temperature_c": _parse_float(temperature),
            }
        )
    return gpus


def collect_gpu_metrics() -> list[dict[str, float | str]]:
    result = subprocess.run(
        [
            "nvidia-smi",
            f"--query-gpu={','.join(QUERY_FIELDS)}",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_nvidia_smi_csv(result.stdout.splitlines())


def _labels(gpu: dict[str, float | str]) -> str:
    name = str(gpu["name"]).replace("\\", "\\\\").replace('"', '\\"')
    return f'gpu="{gpu["gpu"]}",modelName="{name}"'


def render_prometheus(gpus: Iterable[dict[str, float | str]]) -> str:
    lines = [
        "# HELP DCGM_FI_DEV_GPU_UTIL GPU utilization percent from nvidia-smi.",
        "# TYPE DCGM_FI_DEV_GPU_UTIL gauge",
        "# HELP DCGM_FI_DEV_FB_USED Framebuffer memory used in MiB from nvidia-smi.",
        "# TYPE DCGM_FI_DEV_FB_USED gauge",
        "# HELP DCGM_FI_DEV_FB_FREE Framebuffer memory free in MiB from nvidia-smi.",
        "# TYPE DCGM_FI_DEV_FB_FREE gauge",
        "# HELP DCGM_FI_DEV_GPU_TEMP GPU temperature Celsius from nvidia-smi.",
        "# TYPE DCGM_FI_DEV_GPU_TEMP gauge",
    ]
    for gpu in gpus:
        labels = _labels(gpu)
        memory_total = float(gpu["memory_total_mib"])
        memory_used = float(gpu["memory_used_mib"])
        lines.append(f"DCGM_FI_DEV_GPU_UTIL{{{labels}}} {float(gpu['gpu_util_percent'])}")
        lines.append(f"DCGM_FI_DEV_FB_USED{{{labels}}} {memory_used}")
        lines.append(f"DCGM_FI_DEV_FB_FREE{{{labels}}} {max(memory_total - memory_used, 0.0)}")
        lines.append(f"DCGM_FI_DEV_GPU_TEMP{{{labels}}} {float(gpu['temperature_c'])}")
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/metrics", "/"}:
            self.send_error(404)
            return
        try:
            body = render_prometheus(collect_gpu_metrics()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:  # pragma: no cover - exercised in container smoke.
            body = html.escape(str(exc)).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    port = int(os.getenv("NVIDIA_SMI_EXPORTER_PORT", "9400"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MetricsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
