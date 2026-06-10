# รายการ Skill และ Repo ที่ติดตั้งเพิ่ม (สรุปรวม)

สรุปรายการสุดท้าย: skill ที่เก็บไว้ 14 ตัว + repo/tool ที่ติดตั้งเพิ่ม 2 ตัวตอนนี้ (และอีก 3-4 ตัวแนะนำให้ลงภายหลัง)

## Repo ที่ติดตั้งเพิ่ม (ตอนนี้ — 3 ตัว)

| # | Repo | ประเภท | วิธีติดตั้ง |
|---|---|---|---|
| 1 | `JuliusBrussee/caveman` | Skill pack (output token saver, แทน caveman เดิม) | `irm https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.ps1 \| iex` |
| 2 | `chopratejas/headroom` | MCP server (input token compressor) | `pip install "headroom-ai[mcp]"` + `headroom mcp install` |
| 3 | `Egonex-AI/Understand-Anything` | Codebase knowledge graph + dashboard | `iwr -useb https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.ps1 \| iex` → `codex`; แล้ว `pnpm install` ใน `%USERPROFILE%\.understand-anything\repo` |

**Understand-Anything paths:** repo `%USERPROFILE%\.understand-anything\repo`, skills `%USERPROFILE%\.agents\skills\understand*`, plugin root `%USERPROFILE%\.understand-anything-plugin`. Cursor: restart IDE; ถ้า skills ไม่ขึ้น → Settings → Plugins → `https://github.com/Egonex-AI/Understand-Anything`

## Repo แนะนำให้ลงภายหลัง (ยังไม่ติดตั้ง)

| Repo | เหตุผลที่รอ |
|---|---|
| `oraios/serena` | semantic code retrieval — คุ้มเมื่อ codebase โตแล้ว |
| `upstash/context7` | docs ล่าสุดของ Next.js 16 / Drizzle / Playwright — ลงได้เลยถ้าต้องการ |
| `doobidoo/mcp-memory-service` | อาจไม่จำเป็นถ้าใช้ cross-agent memory ของ headroom |

## Skill ที่เก็บไว้ (14 ตัว จาก mattpocock/skills)

| Skill | หมวด | ใช้ทำอะไร |
|---|---|---|
| `diagnose` | engineering | debug แบบมีระเบียบวิธี |
| `grill-with-docs` | engineering | stress-test แผนเทียบกับ docs/ADR |
| `improve-codebase-architecture` | engineering | หาจุด refactor/ปรับ architecture |
| `prototype` | engineering | สร้าง prototype ทดลอง design |
| `review` | engineering | review โค้ดสองแกน (standards + spec) |
| `setup-matt-pocock-skills` | engineering | setup issue tracker ให้ skill อื่น |
| `tdd` | engineering | red-green-refactor |
| `to-issues` | engineering | แตกแผนเป็น issues |
| `to-prd` | engineering | แปลงบริบทเป็น PRD |
| `triage` | engineering | จัดการ issue workflow |
| `zoom-out` | engineering | ดูภาพรวมโค้ด |
| `grill-me` | productivity | สัมภาษณ์เค้นแผนจนเคลียร์ |
| `handoff` | productivity | สรุป conversation ส่งต่อ agent อื่น |
| `setup-pre-commit` | misc | ตั้ง Husky + lint-staged |
| `write-a-skill` | productivity | สร้าง skill ใหม่ |

หมายเหตุ: `caveman` (mattpocock) ถูกถอดออกจากรายการเก็บ — แทนที่ด้วยเวอร์ชัน JuliusBrussee ซึ่งมาพร้อม sub-commands: `/caveman`, `/caveman-commit`, `/caveman-review`, `/caveman-stats`, `/caveman-compress`

## Skill ที่ลบ (14 ตัว)

`caveman` (แทนด้วยเวอร์ชันใหม่), `design-an-interface`, `qa`, `request-refactor-plan`, `ubiquitous-language` (deprecated), `edit-article`, `obsidian-vault`, `writing-beats`, `writing-fragments`, `writing-shape` (สาย writing/personal), `git-guardrails-claude-code`, `migrate-to-shoehorn`, `scaffold-exercises`, `teach` (ไม่เกี่ยวกับโปรเจกต์)

ลบจาก: `.agents/skills/`, `.qoder/skills/` และ entry ใน `skills-lock.json`
