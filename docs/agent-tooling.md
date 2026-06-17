# Agent Tooling — Radio Ad-Sensing Pipeline

> **คู่มือติดตั้ง:** [`final-install-list.md`](../final-install-list.md)  
> **Agent runbook (รันคำสั่งเอง — user ไม่ต้องพิมพ์):** [`.cursor/rules/agent-commands.mdc`](../.cursor/rules/agent-commands.mdc)  
> **Checklist สั้น:** `.cursor/rules/every-session.mdc` · `AGENTS.md` § Every session

---

## ค่าเฉพาะ repo นี้

| รายการ | ค่า |
|---|---|
| Lint / verify | `.venv\Scripts\pytest -q` |
| DB migrate smoke | `.venv\Scripts\python -c "from shared.db import migrate; migrate('data/test.db')"` |
| Graph | `.understand-anything/knowledge-graph.json` |
| Auto-update | `autoUpdate: true` · `.cursor/hooks.json` · `.githooks/post-commit` |
| Operator | `/pipeline-ops` → `.agents/skills/pipeline-ops/SKILL.md` |

**Agent:** รันคำสั่งด้านบนเองตาม trigger ใน `agent-commands.mdc` — อย่าบอก user ให้ copy-paste

---

## Plugin ที่ติดตั้งแล้ว (เครื่อง)

Understand-Anything · Caveman · Headroom · Context7 — ดู `final-install-list.md`

Context7 = library docs เท่านั้น (faster-whisper, Ollama, FastAPI, ffmpeg) — ไม่แทน `/understand-chat`
