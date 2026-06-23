# Linear → Oracle → Agent commit

อ่าน `AGENTS.md`, `project-memory/workflows/git-safety-workflow.md`, และ `project-memory/workflows/linear-oracle-agent-workflow.md` ก่อนเริ่ม

1. ตรวจว่า current diff ยังจำกัดอยู่แค่งาน Linear / Oracle นี้
2. รัน:
   - `git status --short --branch`
   - `git diff --stat`
   - `git diff --name-only`
3. ถ้ามี dirty/untracked files ที่ไม่เกี่ยวข้อง ให้หยุดแล้วถามก่อน
4. ถ้าอยู่บน `main` ให้สร้างและสลับไป `docs/linear-oracle-workflow` ก่อน commit
5. stage เฉพาะไฟล์ที่เกี่ยวกับงานนี้
6. verify staged files
7. commit ด้วย message ที่สั้นและชัด
8. push branch
9. รายงาน commit hash, branch, staged files, และ final git status
10. ห้ามเปิด PR ในคำสั่งนี้
