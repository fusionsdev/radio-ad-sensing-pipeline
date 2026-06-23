# Linear → Oracle → Agent

อ่าน `AGENTS.md`, `project-memory/workflows/git-safety-workflow.md`, และ `project-memory/workflows/linear-oracle-agent-workflow.md` ก่อนเริ่ม

1. อ่าน Linear issue แล้วสรุป:
   - goal
   - scope
   - likely files / areas
   - risks
   - acceptance criteria
2. รัน git preflight:
   - `git status --short --branch`
   - `git branch --show-current`
   - `git diff --stat`
   - `git diff --cached --stat`
3. ถ้าอยู่บน `main` ให้สร้างและสลับไป `docs/linear-oracle-workflow` ก่อนแก้
4. ถ้ามี dirty/untracked files ที่ไม่ใช่ของเดิมในงานนี้ ให้หยุดแล้วถามก่อน
5. Read repo + project-memory files ที่เกี่ยวข้อง
6. ถ้างานเสี่ยงหรือซับซ้อน ให้ consult Oracle โดยส่งเฉพาะ:
   - issue summary
   - focused files / diff
   - exact question
   - constraints
7. บันทึกสรุป Oracle แบบ sanitized กลับเข้า Linear ถ้า policy อนุญาต
8. ทำงานใน branch เฉพาะ
9. test แล้วเปิด PR เมื่อพร้อม
10. อัปเดต Linear ด้วยสถานะ sanitized
11. รายงาน progress แล้วหยุด
