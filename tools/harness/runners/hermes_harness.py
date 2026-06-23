"""Hermes context harness — local Hermes, loan-only, station policy preserved."""

from __future__ import annotations

from pathlib import Path

from tools.harness.lib.common import (
    MANDATORY_MEMORY_FILES,
    PROJECT_ROOT,
    CheckResult,
    HarnessResult,
)

HERMES_PATH = PROJECT_ROOT / ".hermes.md"
AGENTS_PATH = PROJECT_ROOT / "AGENTS.md"
MCP_CONFIG = PROJECT_ROOT / "config" / "obsidian-mcp.json"
CONTRACT_PATH = PROJECT_ROOT / "config" / "agent-memory-contract.md"
CURSOR_RULE = PROJECT_ROOT / ".cursor" / "rules" / "radiosense-memory.mdc"
PIPELINE_OPS_SKILL = PROJECT_ROOT / ".agents" / "skills" / "pipeline-ops" / "SKILL.md"

AGENT_SHIMS = {
    "codex": PROJECT_ROOT / "CODEX.md",
    "claude": PROJECT_ROOT / "CLAUDE.md",
    "grok": PROJECT_ROOT / "GROK.md",
}


def _file_contains(path: Path, needles: list[str]) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, [f"missing file: {path.name}"]
    text = path.read_text(encoding="utf-8").lower()
    missing = [n for n in needles if n.lower() not in text]
    return len(missing) == 0, missing


def run() -> HarnessResult:
    checks: list[CheckResult] = []
    metrics: dict = {}

    memory_missing = [p.name for p in MANDATORY_MEMORY_FILES if not p.exists()]
    checks.append(
        CheckResult(
            name="mandatory_memory_files",
            passed=len(memory_missing) == 0,
            detail="all present" if not memory_missing else f"missing: {', '.join(memory_missing)}",
            recommended_action=None if not memory_missing else "Create project-memory core files",
        )
    )

    hermes_ok, hermes_missing = _file_contains(
        HERMES_PATH,
        ["loan-only", "docker exec radio-worker", "pipeline-loan-ops"],
    )
    checks.append(
        CheckResult(
            name="hermes_loan_policy",
            passed=hermes_ok,
            detail="ok" if hermes_ok else f"missing tokens: {hermes_missing}",
            recommended_action=None if hermes_ok else "Update .hermes.md loan-only runbook",
        )
    )

    agents_ok, agents_missing = _file_contains(
        AGENTS_PATH,
        ["project-memory", "tools/harness/run_all.py", "agent-memory-contract"],
    )
    checks.append(
        CheckResult(
            name="agents_memory_workflow",
            passed=agents_ok,
            detail="ok" if agents_ok else f"missing tokens: {agents_missing}",
            recommended_action=None if agents_ok else "Update AGENTS.md Memory OS section",
        )
    )

    missing_shims = [name for name, path in AGENT_SHIMS.items() if not path.exists()]
    checks.append(
        CheckResult(
            name="agent_shims",
            passed=len(missing_shims) == 0,
            detail="ok" if not missing_shims else f"missing: {', '.join(missing_shims)}",
            recommended_action=None if not missing_shims else "Create CODEX.md, CLAUDE.md, GROK.md shims",
        )
    )

    shim_points_ok = True
    shim_issues: list[str] = []
    for name, path in AGENT_SHIMS.items():
        if not path.exists():
            continue
        ok, missing = _file_contains(path, ["agents.md"])
        if not ok:
            shim_points_ok = False
            shim_issues.append(f"{name}: {missing}")
    checks.append(
        CheckResult(
            name="agent_shims_point_to_agents",
            passed=shim_points_ok,
            detail="ok" if shim_points_ok else f"missing refs: {shim_issues}",
            recommended_action=None if shim_points_ok else "Shims must reference AGENTS.md",
        )
    )

    contract_ok = CONTRACT_PATH.exists()
    checks.append(
        CheckResult(
            name="agent_memory_contract",
            passed=contract_ok,
            detail=str(CONTRACT_PATH) if contract_ok else "config/agent-memory-contract.md missing",
            recommended_action=None if contract_ok else "Create config/agent-memory-contract.md",
        )
    )

    cursor_ok, cursor_missing = _file_contains(
        CURSOR_RULE,
        ["agents.md", "04_agent_load_order", "tools/harness/run_all.py"],
    ) if CURSOR_RULE.exists() else (False, ["radiosense-memory.mdc"])
    checks.append(
        CheckResult(
            name="cursor_memory_rule",
            passed=cursor_ok,
            detail="ok" if cursor_ok else f"missing: {cursor_missing}",
            recommended_action=None if cursor_ok else "Create .cursor/rules/radiosense-memory.mdc",
        )
    )

    preload_needles = [
        "00_project_overview",
        "01_current_architecture",
        "02_operating_policy",
        "03_forbidden_assumptions",
        "04_agent_load_order",
    ]
    hermes_preload_ok, hermes_preload_missing = _file_contains(HERMES_PATH, preload_needles)
    checks.append(
        CheckResult(
            name="hermes_memory_preload",
            passed=hermes_preload_ok,
            detail="ok" if hermes_preload_ok else f"missing: {hermes_preload_missing}",
            recommended_action=None if hermes_preload_ok else "Add project-memory preload to .hermes.md",
        )
    )

    skill_preload_ok, skill_preload_missing = _file_contains(
        PIPELINE_OPS_SKILL,
        preload_needles,
    ) if PIPELINE_OPS_SKILL.exists() else (False, ["pipeline-ops SKILL.md"])
    checks.append(
        CheckResult(
            name="pipeline_ops_memory_preload",
            passed=skill_preload_ok,
            detail="ok" if skill_preload_ok else f"missing: {skill_preload_missing}",
            recommended_action=None if skill_preload_ok else "Add Memory OS preload to pipeline-ops SKILL.md",
        )
    )

    policy_ok, policy_missing = _file_contains(
        AGENTS_PATH,
        ["do not assume", "hermes local", "tools/harness/run_all.py"],
    )
    checks.append(
        CheckResult(
            name="local_ai_policy_documented",
            passed=policy_ok,
            detail="ok" if policy_ok else f"missing: {policy_missing}",
            recommended_action=None if policy_ok else "Document Hermes-local default in AGENTS.md",
        )
    )

    mcp_exists = MCP_CONFIG.exists()
    checks.append(
        CheckResult(
            name="obsidian_mcp_config",
            passed=mcp_exists,
            detail=str(MCP_CONFIG) if mcp_exists else "config/obsidian-mcp.json not found",
            recommended_action=None if mcp_exists else "Add Obsidian MCP config template",
        )
    )
    if mcp_exists:
        import json  # noqa: PLC0415

        cfg = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
        vault_path = cfg.get("vaultPath") or cfg.get("vault_path") or ""
        vault_ok = "project-memory" in vault_path.replace("\\", "/")
        checks.append(
            CheckResult(
                name="mcp_vault_path",
                passed=vault_ok,
                detail=vault_path,
                recommended_action=None if vault_ok else "Point MCP vault to project-memory/",
            )
        )

    metrics["memory_files"] = len(MANDATORY_MEMORY_FILES) - len(memory_missing)
    passed = all(c.passed for c in checks)
    return HarnessResult(harness="hermes", passed=passed, checks=checks, metrics=metrics)