# Smart Connections Setup

Semantic note discovery for `project-memory/` — local embeddings, no API key.

## Installed

- Plugin: **Smart Connections** v4.5.3
- Path: `.obsidian/plugins/smart-connections/`
- Repo: https://github.com/brianpetro/obsidian-smart-connections

## One-time in Obsidian UI

1. **Restart Obsidian** (โหลด plugin ใหม่)
2. **Settings → Community plugins** — ยืนยัน **Smart Connections** เปิดอยู่
3. รอ notice **embedding/index complete** (vault เล็ก — ใช้เวลาไม่นาน)
4. เปิด **Connections view** (ไอคอน ribbon ซ้าย) หรือ `Ctrl+P` → `Open: Connection view`
5. เปิด `00_Project_Overview.md` — ควรเห็น notes ที่เกี่ยวข้อง (Architecture, Policy, ฯลฯ)

## Lookup (semantic search)

`Ctrl+P` → **`Open: Lookup view`** → ค้น เช่น `loan classifier policy` หรือ `hermes pipeline`

## ใช้กับ Memory OS

| งาน | วิธี |
|---|---|
| Agent หา runbook ที่เกี่ยว | Lookup → `watchdog restart` |
| เขียน memory ใหม่ | Connections แนะนำ notes ที่ควร wikilink |
| ตรวจความซ้ำ | เปิด note ใหม่ ดู Connections ก่อน commit |

## Embedding cache

Smart Environment เก็บ index ใน vault (โฟลเดอร์ `.smart-env` หรือใต้ `.obsidian`) — **ไม่ต้อง commit** ลง git

## Related

- [[Obsidian Git Setup]]
- [[04_Agent_Load_Order]]
- [[Decisions/Memory OS Phase 1]]