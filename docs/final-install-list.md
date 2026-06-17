# คู่มือติดตั้ง Agent Tooling (ใช้ซ้ำได้ทุก Project)

เป้าหมาย: **agent จำ codebase ได้ + ประหยัด token**  
อัปเดต: 2026-06-12 · ทดสอบบน Windows + Cursor + Claude Code

---

## ภาพรวม

| ชั้น | ติดตั้งที่ไหน | ทำกี่ครั้ง |
|---|---|---|
| **Machine** | `%USERPROFILE%` (skills, plugins, MCP) | ครั้งเดียวต่อเครื่อง |
| **Project** | root ของ repo (rules, graph, AGENTS.md) | ทุก repo ใหม่ |

---

## สิ่งที่ต้องติดตั้ง

### ชุดหลัก (แนะนำทุก project)

| # | Repo / Plugin | หน้าที่ | ประหยัด |
|---|---|---|---|
| 1 | [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) | Knowledge graph + `/understand-chat` | ไม่ต้องอ่านทั้ง repo |
| 2 | [Caveman](https://github.com/JuliusBrussee/caveman) | `/caveman`, commit/review สั้น | output token |
| 3 | [Headroom](https://github.com/chopratejas/headroom) | MCP + proxy บีบ context | input token |
| 4 | [Context7](https://github.com/upstash/context7) | Cursor plugin — docs library ล่าสุด | ไม่ hallucinate API |

### เสริม (optional)

| Repo | เมื่อไหร่ลง |
|---|---|
| [Serena](https://github.com/oraios/serena) | codebase ใหญ่ / ต้อง LSP symbol search |
| [mcp-memory-service](https://github.com/doobidoo/mcp-memory-service) | ไม่ใช้ Headroom memory — **มักไม่จำเป็น** |

### Skills engineering (mattpocock — เก็บ 15 ตัว)

`diagnose`, `grill-with-docs`, `improve-codebase-architecture`, `prototype`, `review`, `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage`, `zoom-out`, `grill-me`, `handoff`, `setup-pre-commit`, `write-a-skill`

### อย่าติดตั้ง (กิน token / ไม่เกี่ยว project)

`design-an-interface`, `qa`, `request-refactor-plan`, `ubiquitous-language`, `edit-article`, `obsidian-vault`, `writing-beats`, `writing-fragments`, `writing-shape`, `git-guardrails-claude-code`, `migrate-to-shoehorn`, `scaffold-exercises`, `teach`, `caveman` (เวอร์ชัน mattpocock — ใช้ JuliusBrussee แทน)

---

## Phase A — ติดตั้งบนเครื่อง (ครั้งเดียว)

### Prerequisites

- Node.js ≥ 22, pnpm ≥ 10
- Python 3.11+ (merge script ของ Understand-Anything)
- Git

### 1. Caveman

```powershell
irm https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.ps1 | iex
```

Skills ที่ได้: `caveman`, `caveman-commit`, `caveman-review`, `caveman-stats`, `caveman-compress`, `caveman-help`  
Path: `%USERPROFILE%\.agents\skills\caveman*`

### 2. Headroom

```powershell
pip install "headroom-ai[mcp]"
headroom mcp install
```

- MCP ลง Claude/Codex config อัตโนมัติ
- เปิด proxy ตอน session ยาว:

```powershell
headroom proxy --memory --code-graph
# → http://127.0.0.1:8787
```

### 3. Understand-Anything

```powershell
iwr -useb https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.ps1 | iex
cd "$env:USERPROFILE\.understand-anything\repo"
pnpm install
```

Paths:

| สิ่ง | Path |
|---|---|
| Repo | `%USERPROFILE%\.understand-anything\repo` |
| Plugin | `%USERPROFILE%\.understand-anything-plugin` |
| Skills | `%USERPROFILE%\.agents\skills\understand*` |

**Cursor:** Settings → Plugins → Add `https://github.com/Egonex-AI/Understand-Anything` → restart IDE

Skills: `understand`, `understand-chat`, `understand-dashboard`, `understand-diff`, `understand-domain`, `understand-explain`, `understand-knowledge`, `understand-onboard`

### 4. Context7

Cursor → Settings → Plugins → ติดตั้ง **context7-plugin** (marketplace ของ Cursor)

### 5. Serena (optional)

```powershell
# ตาม docs ของ oraios/serena — ติดตั้ง CLI แล้วใช้ per-project
serena init  # ใน root ของ repo
```

---

## Phase B — Bootstrap project ใหม่

ทำทีละ repo หลัง clone / สร้าง project

### B1. Cursor rule — checklist ทุก session

สร้าง `.cursor/rules/every-session.mdc`:

```markdown
---
description: Required agent checklist every session
globs:
alwaysApply: true
---

## เรียกใช้ทุกครั้ง (บังคับ)

| ลำดับ | เรียก | ทำไม |
|---|---|---|
| 1 | **`/understand-chat`** | ถาม graph — **อย่าอ่านทั้ง repo** |
| 2 | **`AGENTS.md`** | กฎ stack / architecture ของ project |
| 3 | **`<LINT_CMD>`** | ก่อนปิดงาน |
| 4 | **`/understand`** | หลัง commit โครงสร้างใหญ่ |

Optional: `/caveman`, `headroom proxy`
```

แทน `<LINT_CMD>` เช่น `pnpm -r lint`, `npm run lint`, `cargo clippy`, `ruff check .`

### B2. AGENTS.md (หรือ CLAUDE.md)

เพิ่ม section ใน root agent instructions:

```markdown
## Every session (required)

| ลำดับ | เรียก | ทำไม |
|---|---|---|
| 1 | `/understand-chat` | ถาม codebase ผ่าน graph |
| 2 | `AGENTS.md` | กฎ project |
| 3 | `<LINT_CMD>` | ก่อนปิดงาน |
| 4 | `/understand` | หลัง refactor ใหญ่ |
```

### B3. .gitignore

```gitignore
# Understand-Anything — commit graph + meta; ignore cache
.understand-anything/intermediate/
.understand-anything/tmp/
.headroom/
```

**Commit ได้:** `.understand-anything/knowledge-graph.json`, `meta.json`, `config.json`, `fingerprints.json`

### B4. Build knowledge graph (ครั้งแรก)

ใน root ของ repo (Cursor / Claude Code):

```
/understand --full
```

หรือ incremental หลัง commit ถัดไป:

```
/understand
```

ตรวจว่ามีไฟล์:

```
.understand-anything/knowledge-graph.json
.understand-anything/meta.json
```

### B5. Serena (optional)

```powershell
cd <project-root>
serena init   # สร้าง .serena/project.yml — ตั้ง languages ให้ตรง stack
```

---

## เรียกใช้ทุกครั้ง (สรุป)

| ลำดับ | เรียก | ทำไม |
|---|---|---|
| 1 | `/understand-chat` | ถาม codebase ผ่าน graph |
| 2 | `AGENTS.md` | กฎ stack / architecture |
| 3 | `<LINT_CMD>` | ก่อนปิดงาน |
| 4 | `/understand` | หลัง commit โครงสร้างใหญ่ |

Optional: `/caveman` (output สั้น), `headroom proxy` (session ยาว)

---

## Quick reference — ประหยัด token

| เป้าหมาย | ใช้ |
|---|---|
| หาไฟล์ / architecture | `/understand-chat` |
| อธิบาย function/file | `/understand-explain` |
| ดู impact หลัง PR | `/understand-diff` |
| Rebuild graph | `/understand` / `/understand --full` |
| Dashboard | `/understand-dashboard` |
| ลด output | `/caveman` |
| ลด input | `headroom proxy` |
| docs ของ library | Context7 MCP |
| symbol LSP | Serena |

---

## Checklist หลังติดตั้ง project

- [ ] `.cursor/rules/every-session.mdc` มี `<LINT_CMD>` ถูกต้อง
- [ ] `AGENTS.md` มี § Every session
- [ ] `.gitignore` ไม่ commit intermediate/tmp
- [ ] `/understand --full` สำเร็จ → มี `knowledge-graph.json`
- [ ] `headroom mcp install` แล้ว (เครื่อง)
- [ ] Context7 plugin เปิดใน Cursor
- [ ] ลบ skill ที่ไม่ใช้จาก `~/.agents/skills/` (ถ้ามี)

---

## Troubleshooting

| อาการ | แก้ |
|---|---|
| `/understand-chat` ไม่มี graph | รัน `/understand --full` ใน repo |
| Skills ไม่ขึ้นใน Cursor | Restart IDE; ติด plugin Understand-Anything |
| Headroom MCP timeout | `headroom proxy` ต้องรันอยู่ |
| นับไฟล์ `.ts` ด้วย `Get-ChildItem -Recurse` ช้า/ผิด | ใช้จำนวนจาก scan ใน `.understand-anything/meta.json` แทน |
| Graph เก่า | `/understand` incremental หรือ `--full` |
| Dashboard crash (`main.tsx` not found) | รันจาก **repo path** ไม่ใช่ junction: `cd %USERPROFILE%\.understand-anything\repo\understand-anything-plugin\packages\dashboard` แล้ว `pnpm dev` |
| ดู graph บน VPS | **`docs/understand-dashboard-vps.md`** — static `/understand/` หรือ SSH tunnel |

---

## ตัวอย่าง: AMNESIA OS

| รายการ | ค่าใน repo นี้ |
|---|---|
| Lint | `pnpm -r lint` |
| Graph | 550 nodes, 856 edges (`.understand-anything/knowledge-graph.json`) |
| รายละเอียดเพิ่ม | `docs/agent-tooling.md` |

---

## ไฟล์อ้างอิงใน repo ตัวอย่าง

| ไฟล์ | ใช้ copy/adapt |
|---|---|
| `docs/final-install-list.md` | คู่มือนี้ |
| `docs/agent-tooling.md` | workflow + paths เฉพาะ project |
| `.cursor/rules/every-session.mdc` | checklist Cursor |
| `AGENTS.md` § Every session | checklist ทุก agent |
