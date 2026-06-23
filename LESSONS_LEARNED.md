# LESSONS_LEARNED.md — RadioSense

This file records mistakes, failed assumptions, debugging lessons, and operational gotchas.
Agents must append here whenever they make a wrong assumption, break something, discover stale state, or fix an incident.

## Entry Template

### YYYY-MM-DD — Short title

**Context**
What was being attempted?

**Mistake / Failed assumption**
What was wrong?

**Impact**
What broke or could have broken?

**Root cause**
Why did it happen?

**Fix**
What changed?

**Prevention**
What should future agents do?

**Related files**
- path/to/file

---

### 2026-06-23 — Dashboard container can serve stale code

**Context**
Dashboard routes existed in source but API returned Not Found or unexpected errors.

**Mistake / Failed assumption**
Assuming source code was the same as the running Docker container.

**Impact**
Agent could waste time debugging correct route registration while the running container is old.

**Root cause**
The dashboard container had been running for days and had not been rebuilt after route changes.

**Fix**
Rebuild/restart the dashboard container and verify boot errors.

**Prevention**
When dashboard behavior does not match source, check container age and rebuild status before changing route code.

**Related files**
- docker-compose.yml
- dashboard/Dockerfile
- dashboard/routes/
- project-memory/Incidents/2026-06-23-memory-api-404-docker.md

---

### 2026-06-23 — Classifier broad keywords created false positives

**Context**
Radio ad keyword detection included broad financial terms.

**Mistake / Failed assumption**
Treating generic financial or commercial terms as consumer personal loan intent.

**Impact**
False positives from tax relief, insurance, car dealers, windows, supplements, and unrelated financial ads.

**Root cause**
Keyword patterns were too broad and not phrase-gated enough.

**Fix**
Use strict phrase-only consumer personal loan patterns with explicit exclusions and tests.

**Prevention**
Any classifier change must include before/after deltas and false-positive review.

**Related files**
- scripts/loan_classifier.py
- worker/keywords.py
- config/consumer_personal_loan_taxonomy.yaml
- tests/

---

### 2026-06-23 — Station health must distinguish bad streams from system failure

**Context**
Some stations produced decode errors or zero valid chunks.

**Mistake / Failed assumption**
Treating all station drops as pipeline failure.

**Impact**
Bad streams can consume attempts and reduce useful transcription capacity.

**Root cause**
Some stream URLs are unstable, blocked, or produce AAC/ffmpeg decode errors.

**Fix**
Probe stations and classify them as keep/pause/rotate based on valid chunks and decode errors.

**Prevention**
Before scaling workers or changing pipeline logic, audit station-level health.

**Related files**
- reports/
- watchdog/
- ingestor/
- project-memory/Stations/Batch Policy.md

---

### 2026-06-23 — Task Master init hangs without -y or API keys

**Context**
Installing Task Master AI and running `task-master init` or `parse-prd`.

**Mistake / Failed assumption**
Assuming init is non-interactive, or that default Anthropic/Perplexity models work without API keys.

**Impact**
CLI appears stuck on prompts; `parse-prd` / `add-task --prompt` fail or hang waiting for cloud providers.

**Root cause**
`task-master init` prompts for project name/rules unless `-y` is passed. Default `config.json` targets Anthropic/Perplexity. RadioSense uses local Ollama.

**Fix**
```bash
task-master init -y --no-git --rules cursor --name RadioSense
task-master models --set-main qwen3:8b --ollama
task-master models --set-research qwen3:8b --ollama
task-master models --set-fallback qwen3:8b --ollama
```
Import tasks manually via `tasks.json` or `add-task --title` (no `--prompt`).

**Prevention**
See `.taskmaster/docs/taskmaster-setup.md`. Use `curl http://127.0.0.1:11434/api/tags` to verify Ollama before AI task commands.

**Related files**
- .taskmaster/config.json
- .cursor/mcp.json
- TASKS.md