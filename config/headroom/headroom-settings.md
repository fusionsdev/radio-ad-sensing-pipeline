# Headroom Settings — RadioSense

## Proxy endpoint

| Setting | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | `8787` |
| URL | `http://127.0.0.1:8787` |

## Assumptions

- Headroom runs as a **local proxy** on the operator workstation
- No cloud Headroom service is required for RadioSense
- Proxy may be offline — harness reports **WARNING**, not hard pipeline failure

## Recommended startup

```powershell
headroom proxy --memory --code-graph
```

## MCP (optional)

Installed separately via `headroom mcp install` — see `final-install-list.md`.

RadioSense does not bundle Headroom in Docker Compose.

## Load order with Memory OS

1. `AGENTS.md`
2. `project-memory/04_Agent_Load_Order.md` + mandatory vault files (compressed via Headroom when proxy is up)
3. Task-specific memory (`LESSONS_LEARNED.md`, `.projectmem/` as needed)

Prefer Headroom-compressed context over re-reading full vault trees in long sessions.