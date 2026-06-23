# TASKS.md — RadioSense

This file is the manual task fallback when Task Master AI is unavailable.

Task planning layer: `.taskmaster/` (initialized — see `.taskmaster/docs/taskmaster-setup.md`).

```bash
task-master list
task-master next
```

## Active

### RS-MEM-001 — Install repo-level agent memory scaffold

**Status:** completed  
**Priority:** high  
**Goal:** Add AGENTS.md sections, project-memory scaffold files, LESSONS_LEARNED.md, Cursor/Claude rules, TASKS.md, RUNBOOK.md.  
**Done when:** Files exist, no runtime behavior changed, and focused validation passes.

## Backlog

### RS-TM-001 — Initialize Task Master AI

**Status:** done  
**Priority:** medium  
**Goal:** Initialize Task Master AI for RadioSense and import active tasks.  
**Done:** `.taskmaster/` created, Ollama `qwen3:8b` configured, 7 tasks in `tasks.json`, MCP merged with Obsidian.  
**Risk:** Do not let Task Master overwrite project files.

### RS-PMEM-001 — Initialize projectmem

**Status:** done  
**Priority:** medium  
**Goal:** Add projectmem if compatible with current agent stack.  
**Done:** `projectmem@0.1.5` in `.venv`, `pjm init --no-claude-md`, chained hooks, MCP in `.cursor/mcp.json`.  
**See:** `project-memory/projectmem-evaluation.md`, `project-memory/projectmem-hook-policy.md`

### RS-MEM-002 — Import RS-MEM tasks into Task Master

**Status:** todo  
**Priority:** low  
**Goal:** Mirror RS-MEM-001 … RS-MEM-005 and RS-PMEM-001 into Task Master when CLI is available.