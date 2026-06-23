# Git safety policy

อ่าน `AGENTS.md` และ `project-memory/workflows/git-safety-workflow.md` ก่อนเริ่ม

1. ตรวจ preflight และรายงานสถานะ git ก่อนแก้:
   - `git status --short --branch`
   - `git branch --show-current`
   - `git diff --stat`
   - `git diff --cached --stat`
2. ถ้าอยู่บน `main` ให้สร้างและสลับไป `docs/agent-git-safety-workflow` ก่อนแก้ไฟล์
3. ถ้ามี dirty/untracked files ที่ไม่ใช่ของเดิมในงานนี้ ให้หยุดแล้วถามก่อน
4. แก้เฉพาะ:
   - `AGENTS.md`
   - `project-memory/workflows/git-safety-workflow.md`
   - `project-memory/04_Agent_Load_Order.md`
5. ทำให้ `AGENTS.md` เป็น pointer สั้นๆ ไปยัง workflow และย้ำว่าเป็น hard gate
6. ทำให้ `project-memory/workflows/git-safety-workflow.md` เป็น policy เต็มแบบ mandatory
7. ทำให้ `project-memory/04_Agent_Load_Order.md` ระบุ workflow นี้เป็น load order บังคับ
8. หลังแก้ ให้รายงาน diff และหยุด
9. ห้าม commit, push, หรือเปิด PR จนกว่าจะมีคำสั่งอนุมัติแยกต่างหาก
