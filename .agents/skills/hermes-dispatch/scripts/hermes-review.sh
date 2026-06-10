#!/usr/bin/env bash
# Dispatch a review bundle to Hermes agent CLI.
# Usage:
#   ./hermes-review.sh wp13 plan/codexplan.md [report_path]

set -euo pipefail

SCOPE="${1:?scope required, e.g. wp13}"
PLAN_PATH="${2:-plan/codexplan.md}"
REPORT_PATH="${3:-}"
DIFF_COMMITS="${DIFF_COMMITS:-5}"

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$REPO_ROOT"

command -v hermes >/dev/null 2>&1 || { echo "hermes CLI not found on PATH" >&2; exit 1; }

timestamp="$(date +%Y%m%d-%H%M)"
bundle="plan/_hermes-bundle-${SCOPE}-${timestamp}.md"
out="plan/hermes-review-${SCOPE}-${timestamp}.md"

{
  echo "# Hermes Review Bundle — ${SCOPE}"
  echo "Generated: $(date -Iseconds)"
  echo ""
  echo "## Git changed files (last ${DIFF_COMMITS} commits)"
  echo '```'
  git diff --name-only "HEAD~${DIFF_COMMITS}..HEAD" 2>/dev/null || echo "(no diff)"
  echo '```'
  echo ""
  echo "## Plan"
  echo "Path: ${PLAN_PATH}"
  if [[ -f "$PLAN_PATH" ]]; then
    echo ""
    cat "$PLAN_PATH"
  fi
  if [[ -n "$REPORT_PATH" && -f "$REPORT_PATH" ]]; then
    echo ""
    echo "## Implementer report"
    echo "Path: ${REPORT_PATH}"
    echo ""
    cat "$REPORT_PATH"
  fi
  echo ""
  echo "## Pytest summary"
  echo '```'
  if [[ -x ".venv/bin/pytest" ]]; then
    .venv/bin/pytest -q 2>&1 | tail -n 8 || true
  else
    pytest -q 2>&1 | tail -n 8 || echo "pytest not available"
  fi
  echo '```'
} >"$bundle"

prompt="Act as independent review gate for scope: ${SCOPE}. Read the bundled markdown. Review Spec + Standards per PLAN.md. End with VERDICT: ship | fix-then-ship | rework"

echo "Dispatching Hermes scope=${SCOPE}"
echo "  input:  ${bundle}"
echo "  output: ${out}"

full_prompt="${prompt}

---
Review bundle:

$(cat "$bundle")"

if command -v hermes >/dev/null 2>&1; then
  hermes -z "$full_prompt" --yolo --accept-hooks >"$out"
else
  echo "hermes CLI not found" >&2
  exit 1
fi
echo "Review saved: ${out}"
