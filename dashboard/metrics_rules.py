"""Deterministic interpretation rules for RadioSense Metrics Interpreter."""

from __future__ import annotations

from typing import Any, Literal

MetricStatus = Literal["ok", "warning", "critical", "unknown"]

STATUS_RANK = {"unknown": 0, "ok": 1, "warning": 2, "critical": 3}

ASR_P95_WARNING_SECONDS = 30.0
ASR_P95_CRITICAL_SECONDS = 120.0
GPU_MEMORY_WARNING_RATIO = 0.85
GPU_MEMORY_CRITICAL_RATIO = 0.98
GPU_UTIL_WARNING_PERCENT = 95.0


def worst_status(*statuses: MetricStatus) -> MetricStatus:
    return max(statuses, key=lambda s: STATUS_RANK[s])


def interpret_queue_pressure(
    *,
    pending: int,
    processing: int,
    done: int,
    dropped: int,
    drop_ratio: float,
) -> dict[str, Any]:
    if pending >= 500 or drop_ratio >= 3.0:
        status: MetricStatus = "critical"
        interpretation = "Worker capacity is not keeping up with ingest volume."
        actions = [
            "Check worker throughput and ASR latency.",
            "Reduce active stations if queue pressure stays high.",
            "Review dropped chunk trend in Grafana.",
        ]
    elif pending >= 50 or drop_ratio >= 1.0:
        status = "warning"
        interpretation = "Queue pressure is elevated; worker may be falling behind ingest."
        actions = [
            "Monitor pending count over the next few minutes.",
            "Check worker throughput and ASR latency.",
            "Consider reducing active stations if pressure persists.",
        ]
    else:
        status = "ok"
        interpretation = "Queue depth and drop ratio are within normal bounds."
        actions = ["Continue monitoring queue trends in Grafana."]

    return {
        "status": status,
        "interpretation": interpretation,
        "recommended_actions": actions,
        "metrics": {
            "pending": pending,
            "processing": processing,
            "done": done,
            "dropped": dropped,
            "drop_ratio": round(drop_ratio, 2),
        },
    }


def interpret_worker_throughput(
    *,
    chunks_per_min: float | None,
    pending: int,
    processing: int,
) -> dict[str, Any]:
    worker_active = (chunks_per_min or 0) > 0 or processing > 0

    if pending > 0 and not worker_active:
        status: MetricStatus = "critical"
        interpretation = "Pending chunks exist but the worker does not appear to be processing."
        actions = [
            "Check worker container logs and restart the worker service.",
            "Verify GPU/ASR dependencies are healthy.",
            "Inspect Prometheus worker scrape target.",
        ]
    elif pending >= 50 and worker_active:
        status = "warning"
        interpretation = (
            "Worker is processing, but queue drops or pending depth suggest ingest volume is still too high."
        )
        actions = [
            "Compare worker throughput to ingest rate.",
            "Check ASR latency for bottlenecks.",
            "Reduce active stations if pending keeps rising.",
        ]
    elif worker_active:
        status = "ok"
        interpretation = "Worker is processing and queue pending appears stable."
        actions = ["Continue monitoring throughput vs ingest rate."]
    else:
        status = "ok"
        interpretation = "Queue is idle; no worker activity required right now."
        actions = ["No immediate worker action required."]

    metrics: dict[str, Any] = {
        "pending": pending,
        "processing": processing,
    }
    if chunks_per_min is not None:
        metrics["chunks_per_min"] = round(chunks_per_min, 1)

    return {
        "status": status,
        "interpretation": interpretation,
        "recommended_actions": actions,
        "metrics": metrics,
    }


def interpret_asr_latency(
    *,
    p50_seconds: float | None,
    p95_seconds: float | None,
    pending: int,
    prometheus_available: bool,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if p50_seconds is not None:
        metrics["p50_seconds"] = round(p50_seconds, 2)
    if p95_seconds is not None:
        metrics["p95_seconds"] = round(p95_seconds, 2)

    if p95_seconds is None:
        status: MetricStatus = "unknown"
        if prometheus_available:
            interpretation = "ASR latency metric is not available from Prometheus."
        else:
            interpretation = (
                "ASR latency metric is not available; Prometheus is unreachable."
            )
        actions = [
            "Verify worker metrics endpoint on :9102.",
            "Check pipeline_asr_duration_seconds in Prometheus.",
        ]
    elif p95_seconds >= ASR_P95_CRITICAL_SECONDS and pending >= 50:
        status = "critical"
        interpretation = "ASR p95 latency is very high while the queue is rising."
        actions = [
            "Inspect worker GPU load and Whisper model settings.",
            "Reduce concurrent ingest or active stations.",
            "Review ASR RTF panels in Grafana.",
        ]
    elif p95_seconds >= ASR_P95_WARNING_SECONDS:
        status = "warning"
        interpretation = "ASR p95 latency is elevated and may limit throughput."
        actions = [
            "Check GPU utilization and ASR real-time factor.",
            "Review recent worker errors in logs.",
        ]
    else:
        status = "ok"
        interpretation = "ASR latency is within expected bounds."
        actions = ["Continue monitoring ASR p95 during peak ingest."]

    return {
        "status": status,
        "interpretation": interpretation,
        "recommended_actions": actions,
        "metrics": metrics,
    }


def interpret_gpu_health(
    *,
    utilization_percent: float | None,
    memory_used_bytes: float | None,
    memory_total_bytes: float | None,
    prometheus_available: bool,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if utilization_percent is not None:
        metrics["utilization_percent"] = round(utilization_percent, 1)
    if memory_used_bytes is not None and memory_total_bytes and memory_total_bytes > 0:
        metrics["memory_used_gb"] = round(memory_used_bytes / (1024**3), 1)
        metrics["memory_total_gb"] = round(memory_total_bytes / (1024**3), 1)
        metrics["memory_used_ratio"] = round(memory_used_bytes / memory_total_bytes, 2)

    if utilization_percent is None and memory_used_bytes is None:
        status: MetricStatus = "unknown"
        if prometheus_available:
            interpretation = (
                "GPU metrics are unavailable. Check dcgm-exporter or Prometheus scrape config."
            )
        else:
            interpretation = "GPU metrics are unavailable; Prometheus is unreachable."
        actions = [
            "Verify dcgm-exporter or pipeline_gpu_* metrics on the worker job.",
            "Check nvidia-smi inside the worker container.",
        ]
    else:
        mem_ratio = (
            memory_used_bytes / memory_total_bytes
            if memory_used_bytes is not None and memory_total_bytes and memory_total_bytes > 0
            else None
        )
        if mem_ratio is not None and mem_ratio >= GPU_MEMORY_CRITICAL_RATIO:
            status = "critical"
            interpretation = "GPU memory is nearly exhausted."
            actions = [
                "Restart worker if memory is stuck.",
                "Reduce batch size or concurrent ASR work.",
            ]
        elif (
            (mem_ratio is not None and mem_ratio >= GPU_MEMORY_WARNING_RATIO)
            or (utilization_percent is not None and utilization_percent >= GPU_UTIL_WARNING_PERCENT)
        ):
            status = "warning"
            interpretation = "GPU is under heavy load or memory pressure is building."
            actions = [
                "Watch GPU memory and utilization trends in Grafana.",
                "Avoid adding stations until headroom improves.",
            ]
        else:
            status = "ok"
            interpretation = "GPU is active but not fully saturated."
            actions = ["Continue monitoring GPU panels during peak load."]

    return {
        "status": status,
        "interpretation": interpretation,
        "recommended_actions": actions,
        "metrics": metrics,
    }


def interpret_station_ingest(
    *,
    live: int,
    enabled: int,
    stale: int,
    down: int,
    recovery_events: int = 0,
) -> dict[str, Any]:
    live_ratio = live / enabled if enabled > 0 else 0.0
    metrics = {
        "live": live,
        "enabled": enabled,
        "stale": stale,
        "down": down,
        "live_ratio_percent": round(live_ratio * 100, 1),
        "recovery_events_24h": recovery_events,
    }

    if enabled > 0 and live_ratio < 0.5:
        status: MetricStatus = "critical"
        interpretation = "Less than half of enabled stations are live; ingest coverage is severely degraded."
        actions = [
            "Review stale/down stations and restart or rotate.",
            "Check ingestor logs for stream failures.",
        ]
    elif stale > 0 or down > 0:
        status = "warning"
        interpretation = "Some streams may be unstable."
        actions = [
            "Inspect stale/down stations on Live Stations page.",
            "Review watchdog recovery events.",
            "Probe or rotate affected stations.",
        ]
    else:
        status = "ok"
        interpretation = "Station ingest health looks good."
        actions = ["Continue routine station monitoring."]

    return {
        "status": status,
        "interpretation": interpretation,
        "recommended_actions": actions,
        "metrics": metrics,
    }


def interpret_service_health(
    *,
    db_reachable: bool,
    backend_ok: bool,
    services_up: dict[str, bool] | None,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "db_reachable": db_reachable,
        "backend_ok": backend_ok,
    }
    actions: list[str] = []

    critical_services = {"worker", "ingestor"}
    optional_services = {"alerter", "watchdog", "prometheus", "grafana"}

    if services_up:
        metrics["services"] = services_up

    if not backend_ok or not db_reachable:
        status: MetricStatus = "critical"
        interpretation = "Core backend or database is unavailable."
        actions = [
            "Check dashboard container and SQLite volume.",
            "Verify /health returns db_reachable=true.",
        ]
    elif services_up and any(not services_up.get(s, True) for s in critical_services):
        status = "critical"
        down = [s for s in critical_services if not services_up.get(s, True)]
        interpretation = f"Critical pipeline service(s) down: {', '.join(sorted(down))}."
        actions = [
            "Restart affected Docker services.",
            "Check Prometheus up{} targets for scrape failures.",
        ]
    elif services_up and any(not services_up.get(s, True) for s in optional_services):
        status = "warning"
        down = [s for s in optional_services if not services_up.get(s, True)]
        interpretation = f"Optional service(s) unavailable: {', '.join(sorted(down))}."
        actions = ["Review monitoring stack; pipeline may still operate."]
    else:
        status = "ok"
        interpretation = "Core services appear healthy."
        actions = ["Continue routine health checks."]

    return {
        "status": status,
        "interpretation": interpretation,
        "recommended_actions": actions,
        "metrics": metrics,
    }
