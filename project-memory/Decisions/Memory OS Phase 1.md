# Decision: Memory OS Phase 1

**Date:** 2026-06-23  
**Status:** Accepted

## Context

Agents lose context between sessions. RadioSense needs persistent, versioned project memory with automated verification.

## Decision

Phase 1 delivers:

1. **Obsidian vault** at `project-memory/` (in-repo, git-synced)
2. **MCP access** via obsidian-mcp-server (config template in `config/obsidian-mcp.json`)
3. **Harness** at `tools/harness/` — read-only verification, no prod DB mutations
4. **AGENTS.md** mandates load-before / harness-after workflow

## Deferred (Phase 2)

- zvec semantic index — architecture hooks in `tools/memory/zvec_hooks.py` only
- Smart Connections plugin — operator installs in Obsidian desktop
- obsidian-git auto-sync — operator configures per `docs/obsidian-memory-os-setup.md`

## Related

- [[01_Current_Architecture]]
- [[Glossary]]