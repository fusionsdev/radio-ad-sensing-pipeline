import json
import os
import glob
from collections import defaultdict

base = os.path.expanduser("~/.claude-octopus")

QUERY_MID = {"codex": 0.08, "gemini": 0.02, "perplexity": 0.03, "qwen": 0.02}


def calc_cost(agent: str, tin: int, tout: int, status: str) -> float:
    if status == "failed" and agent in QUERY_MID:
        return QUERY_MID[agent]
    if status != "ok":
        return 0.0
    if agent.startswith("claude"):
        if "opus" in agent:
            rin, rout = 5.0, 25.0
        else:
            rin, rout = 0.80, 4.0
        return (tin * rin + tout * rout) / 1_000_000
    if agent in QUERY_MID:
        return QUERY_MID[agent]
    return 0.0


canonical = os.path.join(base, "runs", "b0b1cae5-ce07-4212-a5b8-33847542d2e0", "agents.jsonl")
files = [canonical] if os.path.exists(canonical) else glob.glob(
    os.path.join(base, "runs", "**", "agents.jsonl"), recursive=True
)
records = []
for path in sorted(set(files)):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

invocations = {}
for r in records:
    key = r.get("output_file") or f"{r['agent']}:{r['ts']}"
    invocations[key] = r

by_provider = defaultdict(
    lambda: {"tokens_in": 0, "tokens_out": 0, "queries": 0, "cost": 0.0, "success": 0, "fail": 0}
)
by_workflow = defaultdict(lambda: {"providers": set(), "queries": 0, "cost": 0.0})

phase = "unknown"
progress_file = os.path.join(base, "progress.json")
if os.path.exists(progress_file):
    with open(progress_file, encoding="utf-8") as f:
        phase = json.load(f).get("phase", "unknown")

for r in invocations.values():
    agent = r["agent"]
    status = r["status"]
    tin = r.get("tokens_in", 0) or 0
    tout = r.get("tokens_out", 0) or 0
    if status not in ("ok", "failed"):
        continue
    by_provider[agent]["queries"] += 1
    by_provider[agent]["success" if status == "ok" else "fail"] += 1
    by_provider[agent]["tokens_in"] += tin
    by_provider[agent]["tokens_out"] += tout
    cost = calc_cost(agent, tin, tout, status)
    by_provider[agent]["cost"] += cost
    wf = f"/octo:{phase}" if phase != "unknown" else "/octo:probe"
    by_workflow[wf]["providers"].add(agent)
    by_workflow[wf]["queries"] += 1
    by_workflow[wf]["cost"] += cost

tel_counts = defaultdict(int)
tel_file = os.path.join(base, ".octo", "provider-telemetry.jsonl")
if os.path.exists(tel_file):
    with open(tel_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tel_counts[json.loads(line)["provider"]] += 1

session = {}
session_file = os.path.join(base, "metrics-session.json")
if os.path.exists(session_file):
    with open(session_file, encoding="utf-8") as f:
        session = json.load(f)

print("=== PROVIDERS ===")
total_q = 0
total_cost = 0.0
for agent in sorted(by_provider.keys()):
    d = by_provider[agent]
    total_q += d["queries"]
    total_cost += d["cost"]
    print(
        f"{agent}|{d['tokens_in']}|{d['tokens_out']}|{d['queries']}|{d['cost']:.4f}|"
        f"ok={d['success']}|fail={d['fail']}"
    )
print(f"TOTAL|{total_q}|{total_cost:.4f}")

print("=== WORKFLOWS ===")
for wf, d in sorted(by_workflow.items()):
    provs = ",".join(sorted(d["providers"]))
    print(f"{wf}|{provs}|{d['queries']}|{d['cost']:.4f}")

print("=== TELEMETRY ===")
for p, c in sorted(tel_counts.items()):
    print(f"{p}:{c}")

print("=== SESSION ===")
print(json.dumps(session))

if records:
    ts_list = [r["ts"] for r in records if r.get("ts")]
    print(f"FIRST:{min(ts_list)}")
    print(f"LAST:{max(ts_list)}")
