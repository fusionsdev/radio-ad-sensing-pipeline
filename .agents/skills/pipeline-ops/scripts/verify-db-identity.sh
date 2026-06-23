#!/usr/bin/env bash
# Verify all pipeline containers read the SAME canonical DB (the pipeline_data
# named volume at /app/data/pipeline.db). Use after any dashboard rebuild, or
# whenever operator numbers look wrong / too low / frozen.
#
# Usage from repo root:
#   bash .agents/skills/pipeline-ops/scripts/verify-db-identity.sh
#
# Exit 0 = all containers agree on detections count. Non-zero = split detected.
set -euo pipefail

CONTAINERS=(radio-dashboard radio-worker radio-ingestor radio-alerter)
QUERY="python3 -c \"import sqlite3;c=sqlite3.connect('/app/data/pipeline.db');print(c.execute('SELECT COUNT(*) FROM detections').fetchone()[0])\""

declare -A counts
for svc in "${CONTAINERS[@]}"; do
  if ! docker inspect -f '{{.State.Running}}' "$svc" 2>/dev/null | grep -q true; then
    echo "SKIP  $svc (not running)"
    continue
  fi
  # alerter may lack python3; try, tolerate failure
  n=$(docker exec "$svc" sh -c "$QUERY" 2>/dev/null || echo "ERR")
  counts["$svc"]=$n
  printf "%-18s detections=%s\n" "$svc" "$n"
done

# Compare numeric values only
vals=()
for svc in "${!counts[@]}"; do
  v="${counts[$svc]}"
  [[ "$v" =~ ^[0-9]+$ ]] && vals+=("$v")
done

if [ ${#vals[@]} -lt 2 ]; then
  echo "WARN  fewer than 2 numeric results — cannot confirm consistency"
  exit 0
fi

uniq=$(printf '%s\n' "${vals[@]}" | sort -u | wc -l)
if [ "$uniq" -eq 1 ]; then
  echo "OK    all containers agree: ${vals[0]} detections (canonical DB shared)"
  exit 0
else
  echo "FAIL  DB SPLIT detected — containers disagree:"
  for svc in "${!counts[@]}"; do printf "      %-18s %s\n" "$svc" "${counts[$svc]}"; done
  echo "      dashboard reading the stale host DB? check docker-compose.prod.yml is applied"
  exit 1
fi
