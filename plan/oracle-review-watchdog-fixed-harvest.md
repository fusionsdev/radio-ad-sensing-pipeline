ติดตั้ง Oracle CLI ให้ลองแบบนี้ครับ

**1. เช็ก Node ก่อน**

Oracle ต้องใช้ Node รุ่นใหม่มาก แนะนำ Node `24+`

```powershell
node -v
npm -v
```

ถ้า Node ต่ำกว่า 24 ให้ลงผ่าน `nvm-windows` หรือ installer จาก Node.js ก่อน

**2. ติดตั้ง Oracle CLI**

```powershell
npm install -g @steipete/oracle
```

เช็กว่าใช้ได้:

```powershell
oracle --help
```

Oracle รองรับการเรียกผ่าน CLI และ `npx` ด้วย

**3. ทดสอบถาม ChatGPT/Gemini**

แบบ browser mode:

```powershell
oracle "Say hello and return only OK"
```

ถ้ามันต้องเปิด browser ให้ login ChatGPT/Gemini ให้เรียบร้อยก่อน

**4. ใช้กับ Codex Desktop**

ใน repo Radio Pipeline ให้เพิ่ม rule ใน `AGENTS.md` หรือ memory/skill ของโปรเจกต์:

```md
## Oracle Review Rule

When asked to get external review, use Oracle CLI.

Use Oracle only for:
- design review
- diff review
- go/no-go review
- risk review
- test gap review

Do not use Oracle to deploy, restart services, mutate live DB, enable stations, or scale workers.

Save report first to:
plan/latest-report.md

Then ask Oracle:

oracle "Review plan/latest-report.md for Radio Pipeline. Return go/no-go, risks, and next action. Do not approve live deploy unless safe."

Save response to:
plan/latest-oracle-review.md
```

**5. Prompt ให้ Codex ใช้ Oracle**

```md
# Use Oracle For Review

Read `plan/latest-report.md`.

Ask Oracle CLI to review it for:
- go/no-go
- risks
- scope creep
- missing tests
- next safest action

Save Oracle output to:
plan/latest-oracle-review.md

Do not deploy.
Do not restart services.
Do not mutate live DB.
Do not change station set.
```

**คำแนะนำสำหรับคุณ**

เริ่มทดลองกับงาน read-only ก่อน เช่น:

```text
Patch E.1 report review
watchdog audit report review
KLIF/WBAP ingest report review
```

อย่าให้ Oracle/Codex ตัดสินใจ deploy เองตอนคุณไม่อยู่ ให้มันแค่ review + เขียน report กลับมา.
