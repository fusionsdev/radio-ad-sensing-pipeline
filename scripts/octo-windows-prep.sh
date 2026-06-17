#!/usr/bin/env bash
# Idempotent Octo prep for Windows (Git Bash). Source before orchestrate.sh.
set -euo pipefail

octo_user="${USER:-${USERNAME:-unknown}}"
octo_session="${CLAUDE_CODE_SESSION:-global}"

# Git Bash on Windows: ensure /tmp exists (Octo writes model cache here).
if [[ ! -d /tmp ]]; then
  mkdir -p /tmp 2>/dev/null || {
    export TMPDIR="${TMPDIR:-${TEMP:-/tmp}}"
    mkdir -p "$TMPDIR"
  }
fi

# Prevent model-resolver.sh line 234 noise when cache file is missing.
cache_file="/tmp/octo-model-cache-${octo_user}-${octo_session}.json"
if [[ ! -f "$cache_file" ]]; then
  echo '{}' >"$cache_file"
fi

# Gemini headless runs fail without trusted workspace on this repo.
export GEMINI_CLI_TRUST_WORKSPACE="${GEMINI_CLI_TRUST_WORKSPACE:-true}"

# Cold Gemini/Codex invocations often exceed the default 120s grasp timeout on Windows.
export OCTOPUS_AGENT_TIMEOUT="${OCTOPUS_AGENT_TIMEOUT:-300}"
export OCTOPUS_GEMINI_SMOKE_TIMEOUT="${OCTOPUS_GEMINI_SMOKE_TIMEOUT:-60}"

# Ensure Octo config dir exists (first-run wizard creates providers.json).
mkdir -p "${HOME}/.claude-octopus/config" "${HOME}/.claude-octopus/results"

if [[ ! -f "${HOME}/.claude-octopus/config/providers.json" ]]; then
  echo "WARN: ~/.claude-octopus/config/providers.json missing — run orchestrate.sh octopus-configure once." >&2
fi

echo "Octo Windows prep OK (cache=${cache_file}, agent_timeout=${OCTOPUS_AGENT_TIMEOUT})"
