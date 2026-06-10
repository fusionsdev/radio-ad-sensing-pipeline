#!/usr/bin/env python3
"""Phase 4-7: layers, tour, validate, save knowledge graph."""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
INTER = ROOT / ".understand-anything" / "intermediate"
assembled_path = INTER / "assembled-graph.json"
scan_path = INTER / "scan-result.json"

assembled = json.loads(assembled_path.read_text(encoding="utf-8"))
scan = json.loads(scan_path.read_text(encoding="utf-8"))
nodes = assembled["nodes"]
edges = assembled["edges"]
node_ids = {n["id"] for n in nodes}

file_level_types = {"file", "config", "document", "service", "pipeline", "table", "schema", "resource", "endpoint"}


def classify_layer(node: dict) -> str:
    fp = node.get("filePath", "")
    top = fp.split("/")[0] if "/" in fp else fp.split("\\")[0] if "\\" in fp else ""
    if top in ("shared", "config"):
        return "layer:shared-core"
    if top == "ingestor":
        return "layer:ingestor"
    if top == "worker":
        return "layer:worker"
    if top == "alerter":
        return "layer:alerter"
    if top == "dashboard":
        return "layer:dashboard"
    if top == "monitoring":
        return "layer:observability"
    if top == "tests":
        return "layer:tests"
    if top in (".github",) or "Dockerfile" in fp or "docker-compose" in fp:
        return "layer:infrastructure"
    if top in ("plan", ".agents", ".cursor", ".windsurf") or fp in ("README.md", "PLAN.md", "AGENTS.md"):
        return "layer:documentation"
    if top == "scripts":
        return "layer:scripts"
    return "layer:other"


layer_defs = {
    "layer:shared-core": ("Shared Core", "DB, models, config, logging, metrics — import-light foundation used by all services."),
    "layer:ingestor": ("Ingestor", "FFmpeg stream capture, chunk enqueue, station supervisor."),
    "layer:worker": ("Worker", "ASR transcription, LLM extraction, dedup, fingerprinting, janitor."),
    "layer:alerter": ("Alerter", "Telegram outbound alerts for new ads and station health."),
    "layer:dashboard": ("Dashboard", "FastAPI read-only UI for ads, stations, gaps, and health."),
    "layer:observability": ("Observability", "Prometheus, Grafana, and alert rule configuration."),
    "layer:infrastructure": ("Infrastructure", "Dockerfiles, compose, and deployment wiring."),
    "layer:tests": ("Tests", "Pytest modules and fixtures validating pipeline behavior."),
    "layer:documentation": ("Documentation", "Plans, agent skills, conventions, and handoff reports."),
    "layer:scripts": ("Scripts", "Operator utilities outside main service loops."),
    "layer:other": ("Other", "Miscellaneous project files."),
}

buckets: dict[str, list[str]] = {k: [] for k in layer_defs}
for n in nodes:
    if n["type"] not in file_level_types:
        continue
    lid = classify_layer(n)
    if n["id"] in node_ids:
        buckets.setdefault(lid, []).append(n["id"])

layers = []
for lid, (name, desc) in layer_defs.items():
    ids = sorted(set(buckets.get(lid, [])))
    if not ids:
        continue
    layers.append({"id": lid, "name": name, "description": desc, "nodeIds": ids})

# Guided tour — dependency order for onboarding
tour_specs = [
    (1, "Project Overview", "Start with README and AGENTS.md to understand purpose and current ship status.", ["document:README.md", "document:AGENTS.md", "document:PLAN.md"]),
    (2, "Shared Foundation", "SQLite WAL, models, config loaders, and metrics shared by every service.", ["file:shared/db.py", "file:shared/models.py", "file:shared/config.py", "config:config/settings.yaml"]),
    (3, "Stream Ingestion", "How radio streams become WAV chunks in the queue.", ["file:ingestor/supervisor.py", "file:ingestor/ffmpeg.py", "file:ingestor/repository.py", "config:config/stations.yaml"]),
    (4, "Worker Pipeline", "Transcription, LLM extraction, dedup, and fingerprint fast-path.", ["file:worker/consumer.py", "file:worker/transcribe.py", "file:worker/extract.py", "file:worker/dedup.py", "file:worker/fingerprint.py"]),
    (5, "Alerting", "Telegram notifications when new loan/funding ads are detected.", ["file:alerter/service.py", "file:alerter/__main__.py"]),
    (6, "Operator Dashboard", "Browse detections, stations, gaps, and ad detail in the FastAPI UI.", ["file:dashboard/main.py", "file:dashboard/queries.py"]),
    (7, "Observability", "Prometheus metrics and Grafana dashboards for pipeline health.", ["config:monitoring/prometheus.yml", "config:monitoring/grafana/dashboards/pipeline.json"]),
    (8, "Deployment", "Docker Compose multi-service layout for production.", ["service:docker-compose.yml", "service:ingestor/Dockerfile", "service:worker/Dockerfile"]),
]

tour = []
for order, title, desc, refs in tour_specs:
    node_ids_step = [r for r in refs if r in node_ids]
    if node_ids_step:
        tour.append({"order": order, "title": title, "description": desc, "nodeIds": node_ids_step})

import subprocess
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

graph = {
    "version": "1.0.0",
    "project": {
        "name": scan["name"],
        "languages": scan["languages"],
        "frameworks": scan["frameworks"],
        "description": scan["description"],
        "analyzedAt": datetime.now(timezone.utc).isoformat(),
        "gitCommitHash": commit,
    },
    "nodes": nodes,
    "edges": edges,
    "layers": layers,
    "tour": tour,
}

# Inline validation
issues = []
for layer in layers:
    for nid in layer.get("nodeIds", []):
        if nid not in node_ids:
            issues.append(f"Layer {layer['id']} refs missing {nid}")
for step in tour:
    for nid in step.get("nodeIds", []):
        if nid not in node_ids:
            issues.append(f"Tour step {step['order']} refs missing {nid}")

assigned = set()
for layer in layers:
    for nid in layer["nodeIds"]:
        if nid in assigned:
            issues.append(f"Node {nid} in multiple layers")
        assigned.add(nid)

file_nodes = [n["id"] for n in nodes if n["type"] in file_level_types]
for nid in file_nodes:
    if nid not in assigned:
        issues.append(f"File node {nid} not in any layer")

review = {
    "issues": issues,
    "warnings": [],
    "stats": {
        "totalNodes": len(nodes),
        "totalEdges": len(edges),
        "totalLayers": len(layers),
        "tourSteps": len(tour),
    },
}

# Auto-fix orphans into layer:other
if issues:
    other = next((l for l in layers if l["id"] == "layer:other"), None)
    if other is None:
        other = {"id": "layer:other", "name": "Other", "description": layer_defs["layer:other"][1], "nodeIds": []}
        layers.append(other)
        graph["layers"] = layers
    for nid in file_nodes:
        if nid not in assigned:
            other["nodeIds"].append(nid)
    issues = [i for i in issues if "not in any layer" not in i]

assembled_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(INTER / "layers.json").write_text(json.dumps(layers, indent=2) + "\n", encoding="utf-8")
(INTER / "tour.json").write_text(json.dumps(tour, indent=2) + "\n", encoding="utf-8")
(INTER / "review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")

out = ROOT / ".understand-anything" / "knowledge-graph.json"
out.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
meta = {"gitCommitHash": commit, "analyzedAt": graph["project"]["analyzedAt"], "nodeCount": len(nodes), "edgeCount": len(edges)}
(ROOT / ".understand-anything" / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
(ROOT / ".understand-anything" / "config.json").write_text(json.dumps({"outputLanguage": "en", "autoUpdate": False}, indent=2) + "\n", encoding="utf-8")

print(f"Saved {out} ({out.stat().st_size // 1024} KB)")
print(f"Nodes: {len(nodes)}, Edges: {len(edges)}, Layers: {len(layers)}, Tour steps: {len(tour)}")
print(f"Issues remaining: {len(issues)}")
