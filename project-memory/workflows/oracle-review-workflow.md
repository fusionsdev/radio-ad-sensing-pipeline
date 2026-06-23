# Oracle Review Workflow

## Purpose

Use Oracle (`@steipete/oracle`) as an external ChatGPT reviewer for complex changes, risky patches, architecture decisions, debugging, and regression analysis.

Oracle is **not** the primary implementer. Codex/Cursor remains responsible for reading the repo, applying patches, running tests, and making final decisions.

---

## Decision Summary

| Topic | Choice |
|-------|--------|
| Default ChatGPT URL | Project root — **new chat per consult** |
| Command style | Short commands; global config supplies browser defaults |
| Full flags | Troubleshooting section only |
| Same conversation | `--followup` within one review session only |
| Module templates | watchdog, worker, ingestor, classifier, dashboard, alerter, scripts |

---

## Prerequisites

### Global config (`~/.oracle/config.json`)

```json
{
  "browser": {
    "manualLogin": true,
    "modelStrategy": "current",
    "keepBrowser": true,
    "archiveConversations": "never",
    "inputTimeoutMs": 120000,
    "chatgptUrl": "https://chatgpt.com/g/g-p-69d42875f768819182dff39bdbb93bc6-radio-ad-pipeline/project"
  }
}
```

| Setting | Why |
|---------|-----|
| `chatgptUrl` → `/project` | Each consult starts a fresh chat inside the Radio Ad Pipeline project |
| `modelStrategy: current` | ChatGPT UI shows Instant/Medium/High/GPT-5.5 — select **High** in browser before run |
| `archiveConversations: never` | Completed chats stay visible |
| `keepBrowser: true` | Oracle Chrome profile persists for login and reattach |

### First-time login (once per machine)

```powershell
oracle -p "HI"
```

Sign in inside the Oracle Chrome window. Select model **High** in the picker.

### Agent integration

- **Skill:** `~/.agents/skills/oracle/SKILL.md`
- **MCP:** `oracle` in Codex (`~/.codex/config.toml`) and Cursor (`~/.cursor/mcp.json`)

---

## Default Engine

**Browser mode only.** Do not use API mode unless the user explicitly approves cost.

All daily commands assume:

```powershell
cd H:\DEV\projects\radio-ad-sensing-pipeline
```

Inherited from global config (omit unless overriding): `--engine browser`, `--browser-manual-login`, `--browser-keep-browser`, `--browser-input-timeout 120000`, `--chatgpt-url` (project root).

---

## When To Use Oracle

**Use Oracle when:**

- touching `watchdog/`, `worker/`, `ingestor/`, `dashboard/`, `shared/`, classifier logic, or DB behavior
- a patch could affect live pipeline stability
- debugging a confusing failure
- deciding between multiple architecture options
- preparing a migration plan
- reviewing a large diff before commit
- writing a final risk report

**Do not use Oracle for:**

- simple typo fixes
- obvious one-line changes
- formatting only
- checks verifiable locally faster

---

## Standard Workflow

1. Inspect the repo locally first.
2. Identify the smallest file set that contains the truth.
3. Preview token/file footprint (`--dry-run summary --files-report`).
4. Run Oracle with a narrow prompt.
5. Save or summarize Oracle's answer in working notes.
6. Accept / reject / modify recommendations.
7. Apply patch locally.
8. Run focused tests.
9. Report what Oracle suggested vs what was implemented.

---

## Preview (no tokens)

```powershell
oracle --dry-run summary --files-report `
  -p "Review watchdog stale station behavior" `
  --file "watchdog/**/*.py" `
  --file "!**/__pycache__/**"
```

---

## Standard Review Command

```powershell
oracle -p "You are an external senior reviewer for the Radio Ad-Sensing Pipeline (Python, Docker, SQLite WAL, ffmpeg ingestor, GPU worker, watchdog). Review the attached files. Return: 1) likely bugs, 2) regression risks for live pipeline, 3) missing tests, 4) recommended patch direction. Be concise and specific." `
  --file "PATH_OR_GLOB"
```

---

## Module Templates

### Watchdog (auto-restart / stale stations)

```powershell
oracle -p "Review watchdog changes. Focus on stale station detection, pool promotion, recovery loops, restart side effects, and missing tests. Findings first, then patch direction." `
  --file "watchdog/**/*.py" `
  --file "tests/**/test_watchdog*.py" `
  --file "!**/__pycache__/**"
```

### Worker (queue / DB / transcription)

```powershell
oracle -p "Review worker changes. Focus on chunk consumption, queue side effects, DB writes under WAL contention, dedup, ASR/LLM path, and missing tests." `
  --file "worker/**/*.py" `
  --file "shared/db.py" `
  --file "shared/migrations/**" `
  --file "tests/**/test_worker*.py" `
  --file "tests/**/test_consumer*.py" `
  --file "!**/__pycache__/**"
```

### Ingestor (streams / chunks / drop rate)

```powershell
oracle -p "Review ingestor changes. Focus on ffmpeg supervision, stream reconnect, chunk write rate, gap logging, backlog drops, and live ingestion safety." `
  --file "ingestor/**/*.py" `
  --file "config/stations.yaml" `
  --file "config/settings.yaml" `
  --file "tests/**/test_ingestor*.py" `
  --file "!**/__pycache__/**"
```

### Classifier (keyword / detection quality)

Classifier logic lives in `worker/`, `shared/`, `config/`, and `scripts/` — not a top-level `classifier/` folder.

```powershell
oracle -p "Review classifier/keyword changes. Focus on false positives, false negatives, loan-vertical rules, rollout safety, and before/after test coverage. Do not treat tax relief, insurance, debt settlement, or car ads as personal loan ads." `
  --file "worker/keyword_classifier_rollout.py" `
  --file "worker/novelty_*.py" `
  --file "shared/consumer_personal_loan.py" `
  --file "shared/keyword_hits_audit.py" `
  --file "config/**/*.yaml" `
  --file "scripts/loan_classifier.py" `
  --file "scripts/replay_classifier_offline.py" `
  --file "tests/**/test_*classifier*.py" `
  --file "tests/**/test_consumer_personal_loan*.py" `
  --file "!**/__pycache__/**"
```

### Dashboard (operator control)

```powershell
oracle -p "Review dashboard changes. Focus on operator control surfaces, read-only SQLite queries, harvest API safety, route correctness, and whether HTML vs JSON contracts changed." `
  --file "dashboard/**/*.py" `
  --file "tests/**/test_dashboard*.py" `
  --file "!**/__pycache__/**"
```

### Alerter (short — lower blast radius)

```powershell
oracle -p "Review alerter changes for alert correctness, duplicate suppression, and unsafe Telegram side effects." `
  --file "alerter/**/*.py" `
  --file "tests/**/test_alerter*.py" `
  --file "!**/__pycache__/**"
```

### Scripts (migration / export / audit)

```powershell
oracle -p "Review operator script changes. Focus on production DB safety, destructive operations, export correctness, and whether scripts assume live pipeline state." `
  --file "scripts/TARGET_SCRIPT.py" `
  --file "RUNBOOK.md" `
  --file "!**/__pycache__/**"
```

---

## Diff Review Template

Identify changed files first (`git diff --name-only`), then:

```powershell
oracle -p "Review the current change set for bugs, regressions, unsafe assumptions, and missing tests. Prioritized findings only." `
  --file "watchdog/recovery.py" `
  --file "watchdog/pool.py" `
  --file "tests/test_watchdog_recovery.py"
```

Replace the file list with actual changed paths.

---

## Follow-up (same review session only)

Use `--followup` when continuing **one** review thread — not as the default for every new consult.

```powershell
oracle status --hours 72

oracle --followup session-4 `
  -p "Follow-up: challenge your previous recommendation with this additional file." `
  --file "watchdog/recovery.py"
```

Or by conversation id from the prior run:

```powershell
oracle --followup CONVERSATION_ID `
  -p "Follow-up: re-evaluate with new context." `
  --file "worker/consumer.py"
```

---

## Large File Sets

```powershell
oracle --browser-bundle-files --browser-bundle-format zip `
  -p "Architecture review of worker + shared DB layer" `
  --file "worker/**/*.py" `
  --file "shared/**/*.py" `
  --file "!**/__pycache__/**"
```

---

## Fallback: Manual Paste

```powershell
oracle --render --copy `
  -p "Review attached watchdog recovery patch" `
  --file "watchdog/recovery.py"
```

Paste from clipboard into the ChatGPT project manually.

---

## Session Management

```powershell
oracle status --hours 72
oracle session <id> --render
```

Transcripts: `~/.oracle/sessions/<id>/artifacts/transcript.md`

---

## API Mode (explicit consent only)

```powershell
oracle doctor --providers --models gpt-5.5-pro

$env:OPENAI_API_KEY = "sk-..."   # user provides

oracle --engine api --provider openai --model gpt-5.5-pro `
  -p "Review watchdog recovery" `
  --file "watchdog/recovery.py"
```

---

## Agent Rules

1. Read repo locally first — Oracle starts with zero project knowledge.
2. Attach only relevant files; never attach `.env`, keys, or `data/pipeline.db`.
3. Prefer `--dry-run summary --files-report` before expensive runs.
4. Default = new project chat per consult; `--followup` only within the same session.
5. Treat Oracle output as advisory — local tests are source of truth.
6. If browser fails, fall back to `--render --copy`.

### Required agent output format

```markdown
## Oracle Consultation

Question asked:
...

Files sent:
...

Oracle summary:
...

Accepted:
...

Rejected:
...

Implementation:
...

Verification:
...
```

---

## Troubleshooting

### Common issues

| Symptom | Fix |
|---------|-----|
| `Unable to find model option matching "Pro"` | Select **High** in ChatGPT; config uses `modelStrategy: current` |
| `No cookies were applied` | Run `oracle -p "HI"` and sign in inside Oracle Chrome |
| Chat disappears after run | Config has `archiveConversations: never`; add `--browser-archive never` if needed |
| Terminal returns immediately | Normal — Oracle is one-shot; answer is in stdout and session artifacts |
| Wrong project/chat | Verify `browser.chatgptUrl` ends in `/project` |

### Full-flag reproduce commands

Use when short commands fail or an agent needs to reproduce browser behavior exactly.

**First-time login:**

```powershell
cd H:\DEV\projects\radio-ad-sensing-pipeline

oracle --engine browser `
  --browser-manual-login `
  --browser-keep-browser `
  --browser-input-timeout 120000 `
  --browser-model-strategy ignore `
  --chatgpt-url "https://chatgpt.com/g/g-p-69d42875f768819182dff39bdbb93bc6-radio-ad-pipeline/project" `
  -p "HI"
```

**Standard review (full flags):**

```powershell
cd H:\DEV\projects\radio-ad-sensing-pipeline

oracle --engine browser `
  --browser-manual-login `
  --browser-keep-browser `
  --browser-input-timeout 120000 `
  --browser-model-strategy current `
  --browser-archive never `
  --chatgpt-url "https://chatgpt.com/g/g-p-69d42875f768819182dff39bdbb93bc6-radio-ad-pipeline/project" `
  -p "Review watchdog stale station behavior" `
  --file "watchdog/**/*.py" `
  --file "tests/**/*.py" `
  --file "!**/__pycache__/**"
```

**Follow-up (full flags):**

```powershell
oracle --engine browser `
  --browser-manual-login `
  --browser-keep-browser `
  --browser-model-strategy current `
  --browser-archive never `
  --followup session-4 `
  -p "Follow-up: re-evaluate with additional context" `
  --file "watchdog/recovery.py"
```

---

## Important Notes

- Oracle answers are advisory, not automatically trusted.
- Browser mode uses the logged-in ChatGPT session; with `modelStrategy: current`, the active picker selection wins.
- Default ignored dirs: `node_modules`, `dist`, `coverage`, `.git`, `build`, `tmp`, `__pycache__` (when not explicitly attached).
- Keep total input under ~196k tokens — use `--files-report` to spot hogs.
- Never attach `.env`, API keys, or production DB files.