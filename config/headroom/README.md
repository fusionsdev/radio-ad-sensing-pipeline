# Headroom — RadioSense Memory OS Phase 1.9

Headroom is the **context compression and shared memory optimization layer** for RadioSense agents. It is not semantic search, RAG, embeddings, or zvec.

## Purpose

- Reduce input token load for long sessions
- Share compressed context across Cursor, Codex, Claude Code, and future Grok
- Complement (not replace) `AGENTS.md`, `project-memory/`, `LESSONS_LEARNED.md`, and `.projectmem/`

## Local proxy (default)

```text
http://127.0.0.1:8787
```

Start (operator machine, optional per session):

```powershell
pip install "headroom-ai[mcp]"
headroom mcp install
headroom proxy --memory --code-graph
```

## Config files

| File | Purpose |
|---|---|
| `headroom-settings.md` | Proxy host/port and operational defaults |
| `agent-routing.md` | Which agents use Headroom and load order |
| `integration-status.md` | Install state, harness results, Hermes notes |

## Verification

```bash
python tools/harness/run_all.py
pytest tests/test_headroom_harness.py
```

Harness runner: `tools/harness/runners/headroom_harness.py`

## Out of scope (Phase 1.9)

- zvec / semantic memory
- Vector database
- RAG pipelines
- Classifier, station rotation, ingestor, or DB schema changes