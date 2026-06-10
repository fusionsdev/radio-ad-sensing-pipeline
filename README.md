# Radio Ad-Sensing Pipeline

Fully local 24/7 pipeline that ingests U.S. News/Talk radio streams, transcribes with faster-whisper, extracts loan/funding ad details with Ollama/Qwen2.5-7B, deduplicates fuzzily, stores in SQLite, and alerts via Telegram.

See [PLAN.md](PLAN.md) for architecture, schema, and implementation phases.

## Implemented

- **Phase 1** — scaffold, SQLite, config, logging
- **WP-4** — worker LLM extraction prompt/schema, Ollama structured-output client, phone normalization
- **WP-5** — fuzzy deduplication/persistence, same-station airing de-dupe window, ad clip boundary estimation/archive hook
- **WP-9** — read-only FastAPI dashboard (`python -m dashboard` → http://127.0.0.1:8080)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev,dashboard]"
pytest
```

## Dashboard

```bash
python -m dashboard
```

## Migrate database

```bash
python -c "from shared.db import migrate; migrate('data/pipeline.db')"
```

## Codebase map (Understand-Anything)

Interactive knowledge graph of this repo. Install once: see `final-install-list.md` § Understand-Anything.

**Cursor (agent skills — type in chat):**

| Command | Purpose |
|---|---|
| `/understand` | Build or refresh `.understand-anything/knowledge-graph.json` |
| `/understand-dashboard` | Open the graph explorer (agent starts Vite) |
| `/understand-chat <question>` | Ask about architecture / flows |
| `/understand-diff` | Impact of current git changes on the graph |
| `/understand-onboard` | Onboarding guide from the graph |
| `/understand-domain` | Business-domain view (domains, flows, steps) |
| `/understand-explain <path>` | Deep-dive one file or symbol |

**PowerShell (from repo root):**

```powershell
.\scripts\setup-understand-auto.ps1       # one-time: enable auto-update hooks
.\scripts\understand-graph-status.ps1   # graph exists? commit, node count
.\scripts\understand-dashboard.ps1      # open dashboard (needs graph + Node/pnpm)
```

**Auto-update (after setup):** `.cursor/hooks.json` tells the Cursor agent to refresh the graph when the repo is stale or after `git commit`. Restart Cursor once after `setup-understand-auto.ps1`.

After `/understand`, optional: commit `.understand-anything/knowledge-graph.json` for teammates (see plugin README; ignore `intermediate/`).
