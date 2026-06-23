"""Metrics Interpreter API: Prometheus wrapper, Grafana links, interpreted summary."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from dashboard import metrics_rules, queries, radiosense_api
from dashboard.metrics_rules import MetricStatus, worst_status

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://127.0.0.1:3000").rstrip("/")
GRAFANA_DASHBOARD_UID = os.getenv("GRAFANA_DASHBOARD_UID", "radio-pipeline")
GRAFANA_DASHBOARD_SLUG = os.getenv("GRAFANA_DASHBOARD_SLUG", "radio-ad-sensing-pipeline")
PROMETHEUS_TIMEOUT_SECONDS = float(os.getenv("PROMETHEUS_TIMEOUT_SECONDS", "3"))

PROMETHEUS_QUERIES: dict[str, str] = {
    "queue_depth": 'sum(pipeline_chunks_by_status{status="pending"})',
    "worker_processing_rate": (
        'sum(rate(pipeline_chunks_processed_total{service="worker"}[5m])) * 60'
    ),
    "asr_latency": (
        "histogram_quantile(0.95, sum(rate(pipeline_asr_duration_seconds_bucket[5m])) by (le))"
    ),
    "gpu_utilization": (
        "max(pipeline_gpu_utilization_percent) or max(DCGM_FI_DEV_GPU_UTIL)"
    ),
    "gpu_memory": "max(pipeline_gpu_memory_used_bytes) or max(DCGM_FI_DEV_FB_USED)",
    "station_ingest_rate": "sum(rate(pipeline_ingest_chunks_total[5m])) * 60",
    "service_up": 'up{job=~"worker|ingestor|dashboard|watchdog|alerter|prometheus"}',
}

GRAFANA_PANEL_IDS: dict[str, int] = {
    "queue_depth": 17,
    "worker_throughput": 2,
    "asr_latency": 11,
    "gpu_utilization": 8,
    "gpu_memory": 9,
    "station_ingest": 13,
    "service_health": 10,
}


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"


def _grafana_dashboard_url() -> str:
    return f"{GRAFANA_URL}/d/{GRAFANA_DASHBOARD_UID}/{GRAFANA_DASHBOARD_SLUG}"


def _grafana_panel_url(panel_id: int) -> str:
    return (
        f"{GRAFANA_URL}/d-solo/{GRAFANA_DASHBOARD_UID}/{GRAFANA_DASHBOARD_SLUG}"
        f"?orgId=1&panelId={panel_id}&theme=dark"
    )


def _section_grafana_url(panel_key: str | None) -> str | None:
    if panel_key and panel_key in GRAFANA_PANEL_IDS:
        return _grafana_panel_url(GRAFANA_PANEL_IDS[panel_key])
    return _grafana_dashboard_url()


def fetch_grafana_links() -> dict[str, Any]:
    base_dashboard = _grafana_dashboard_url()
    dashboards = [
        {"key": "pipeline", "label": "Pipeline Overview", "url": base_dashboard},
        {
            "key": "worker",
            "label": "Worker Metrics",
            "url": f"{base_dashboard}?viewPanel=102",
        },
        {
            "key": "gpu",
            "label": "GPU Metrics",
            "url": f"{base_dashboard}?viewPanel=104",
        },
    ]
    panels = []
    panel_labels = {
        "queue_depth": "Queue Depth",
        "worker_throughput": "Worker Throughput",
        "asr_latency": "ASR Latency",
        "gpu_utilization": "GPU Utilization",
        "gpu_memory": "GPU Memory",
        "station_ingest": "Station Ingest",
    }
    for key, label in panel_labels.items():
        panel_id = GRAFANA_PANEL_IDS.get(key)
        panels.append(
            {
                "key": key,
                "label": label,
                "url": f"{base_dashboard}?viewPanel={panel_id}" if panel_id else base_dashboard,
                "embed_url": _grafana_panel_url(panel_id) if panel_id else None,
            }
        )
    return {
        "base_url": GRAFANA_URL,
        "dashboards": dashboards,
        "panels": panels,
    }


def _prometheus_request(promql: str) -> tuple[bool, dict[str, Any]]:
    query = urllib.parse.urlencode({"query": promql})
    url = f"{PROMETHEUS_URL}/api/v1/query?{query}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PROMETHEUS_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return True, payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return False, {"error": str(exc)}


def _prometheus_query(promql: str) -> tuple[bool, float | None, dict[str, Any]]:
    """Return (available, scalar_value, raw_response)."""
    available, payload = _prometheus_request(promql)
    if not available:
        return False, None, payload

    if payload.get("status") != "success":
        return True, None, payload

    results = payload.get("data", {}).get("result", [])
    if not results:
        return True, None, payload

    if len(results) == 1:
        try:
            return True, float(results[0]["value"][1]), payload
        except (KeyError, TypeError, ValueError):
            return True, None, payload

    return True, None, payload


def _prometheus_query_map(promql: str) -> tuple[bool, dict[str, float], dict[str, Any]]:
    available, payload = _prometheus_request(promql)
    if not available:
        return False, {}, payload

    if payload.get("status") != "success":
        return True, {}, payload

    values: dict[str, float] = {}
    for row in payload.get("data", {}).get("result", []):
        metric = row.get("metric", {})
        job = metric.get("job") or metric.get("service") or metric.get("__name__", "unknown")
        try:
            values[str(job)] = float(row["value"][1])
        except (KeyError, TypeError, ValueError):
            continue
    return True, values, payload


def _prometheus_status_for_value(key: str, value: float | None) -> MetricStatus:
    if value is None:
        return "unknown"
    if key == "queue_depth":
        if value >= 500:
            return "critical"
        if value >= 50:
            return "warning"
        return "ok"
    if key == "worker_processing_rate":
        return "ok" if value > 0 else "warning"
    if key == "asr_latency":
        if value >= metrics_rules.ASR_P95_CRITICAL_SECONDS:
            return "critical"
        if value >= metrics_rules.ASR_P95_WARNING_SECONDS:
            return "warning"
        return "ok"
    if key == "gpu_utilization":
        if value >= metrics_rules.GPU_UTIL_WARNING_PERCENT:
            return "warning"
        return "ok"
    if key == "gpu_memory":
        return "ok"
    if key == "station_ingest_rate":
        return "ok" if value > 0 else "warning"
    if key == "service_up":
        return "ok" if value >= 1 else "critical"
    return "ok"


def fetch_prometheus_metric(key: str) -> dict[str, Any]:
    if key not in PROMETHEUS_QUERIES:
        return {
            "error": f"Unknown metric key: {key}",
            "allowed_keys": sorted(PROMETHEUS_QUERIES.keys()),
        }

    promql = PROMETHEUS_QUERIES[key]
    if key == "service_up":
        available, values, raw = _prometheus_query_map(promql)
        if not available:
            return {
                "key": key,
                "query": promql,
                "value": None,
                "status": "unknown",
                "raw": raw,
                "error": "Prometheus unavailable",
            }
        up_count = sum(1 for v in values.values() if v >= 1)
        return {
            "key": key,
            "query": promql,
            "value": up_count,
            "status": "ok" if up_count > 0 else "warning",
            "services": values,
            "raw": raw,
        }

    available, value, raw = _prometheus_query(promql)
    if not available:
        return {
            "key": key,
            "query": promql,
            "value": None,
            "status": "unknown",
            "raw": raw,
            "error": "Prometheus unavailable",
        }

    return {
        "key": key,
        "query": promql,
        "value": value,
        "status": _prometheus_status_for_value(key, value),
        "raw": raw,
    }


def _queue_counts(db_path) -> dict[str, int]:
    if not queries.db_exists(db_path):
        return {"pending": 0, "processing": 0, "done": 0, "dropped": 0, "drop_ratio": 0.0}
    queue = queries.fetch_queue_health(db_path)
    processing = 0
    try:
        from shared.db import get_connection

        conn = get_connection(db_path, read_only=True)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM chunks WHERE status = 'processing'"
            ).fetchone()
            processing = int(row["cnt"] if row else 0)
        finally:
            conn.close()
    except Exception:
        processing = 0
    return {
        "pending": int(queue.get("pending") or 0),
        "processing": processing,
        "done": int(queue.get("done") or 0),
        "dropped": int(queue.get("dropped") or 0),
        "drop_ratio": float(queue.get("drop_ratio") or 0.0),
    }


def _station_counts(db_path) -> dict[str, int]:
    overview = radiosense_api.fetch_overview_json(db_path)
    stations = overview.get("stations") or {}
    return {
        "live": int(stations.get("live") or 0),
        "enabled": int(stations.get("enabled") or 0),
        "stale": int(stations.get("stale") or 0),
        "down": int(stations.get("down") or 0),
    }


def fetch_metrics_summary(db_path) -> dict[str, Any]:
    warnings: list[str] = []

    _, _, prom_probe = _prometheus_query("up")
    prom_available = "error" not in prom_probe
    if not prom_available:
        warnings.append("Prometheus unavailable; using DB-derived metrics only.")

    queue = _queue_counts(db_path)
    station_counts = _station_counts(db_path)
    health = queries.fetch_health(db_path)

    worker_rate: float | None = None
    asr_p50: float | None = None
    asr_p95: float | None = None
    gpu_util: float | None = None
    gpu_mem_used: float | None = None
    gpu_mem_total: float | None = None
    services_up: dict[str, bool] | None = None

    if prom_available:
        _, worker_rate, _ = _prometheus_query(PROMETHEUS_QUERIES["worker_processing_rate"])
        _, asr_p50, _ = _prometheus_query(
            "histogram_quantile(0.50, sum(rate(pipeline_asr_duration_seconds_bucket[5m])) by (le))"
        )
        _, asr_p95, _ = _prometheus_query(PROMETHEUS_QUERIES["asr_latency"])
        _, gpu_util, _ = _prometheus_query(PROMETHEUS_QUERIES["gpu_utilization"])
        _, gpu_mem_used, _ = _prometheus_query(PROMETHEUS_QUERIES["gpu_memory"])
        _, gpu_mem_total, _ = _prometheus_query(
            "max(pipeline_gpu_memory_total_bytes) or (max(DCGM_FI_DEV_FB_USED) + max(DCGM_FI_DEV_FB_FREE))"
        )
        _, svc_values, _ = _prometheus_query_map(PROMETHEUS_QUERIES["service_up"])
        if svc_values:
            services_up = {name: value >= 1 for name, value in svc_values.items()}

    recovery_events = 0
    if queries.db_exists(db_path):
        try:
            watchdog = radiosense_api.fetch_watchdog_json(db_path)
            recovery_events = len(watchdog.get("recovery_events") or [])
        except Exception:
            recovery_events = 0

    queue_interp = metrics_rules.interpret_queue_pressure(**queue)
    worker_interp = metrics_rules.interpret_worker_throughput(
        chunks_per_min=worker_rate,
        pending=queue["pending"],
        processing=queue["processing"],
    )
    asr_interp = metrics_rules.interpret_asr_latency(
        p50_seconds=asr_p50,
        p95_seconds=asr_p95,
        pending=queue["pending"],
        prometheus_available=prom_available,
    )
    gpu_interp = metrics_rules.interpret_gpu_health(
        utilization_percent=gpu_util,
        memory_used_bytes=gpu_mem_used,
        memory_total_bytes=gpu_mem_total,
        prometheus_available=prom_available,
    )
    station_interp = metrics_rules.interpret_station_ingest(
        live=station_counts["live"],
        enabled=station_counts["enabled"],
        stale=station_counts["stale"],
        down=station_counts["down"],
        recovery_events=recovery_events,
    )
    service_interp = metrics_rules.interpret_service_health(
        db_reachable=bool(health.get("db_reachable")),
        backend_ok=True,
        services_up=services_up,
    )

    sections = [
        {
            "key": "queue_pressure",
            "label": "Queue Pressure",
            "grafana_url": _section_grafana_url("queue_depth"),
            **queue_interp,
        },
        {
            "key": "worker_throughput",
            "label": "Worker Throughput",
            "grafana_url": _section_grafana_url("worker_throughput"),
            **worker_interp,
        },
        {
            "key": "asr_latency",
            "label": "ASR / Transcription Latency",
            "grafana_url": _section_grafana_url("asr_latency"),
            **asr_interp,
        },
        {
            "key": "gpu_health",
            "label": "GPU Health",
            "grafana_url": _section_grafana_url("gpu_utilization"),
            **gpu_interp,
        },
        {
            "key": "station_ingest",
            "label": "Station Ingest Health",
            "grafana_url": _section_grafana_url("station_ingest"),
            **station_interp,
        },
        {
            "key": "service_health",
            "label": "Service Health",
            "grafana_url": _section_grafana_url("service_health"),
            **service_interp,
        },
    ]

    section_statuses = [s["status"] for s in sections if s["status"] != "unknown"]
    if not section_statuses:
        overall: MetricStatus = "unknown"
    else:
        overall = worst_status(*section_statuses)  # type: ignore[arg-type]

    return {
        "generated_at": _now_iso(),
        "overall_status": overall,
        "prometheus_available": prom_available,
        "sections": sections,
        "warnings": warnings,
    }
