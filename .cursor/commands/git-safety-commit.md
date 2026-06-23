# Git safety commit

อ่าน `AGENTS.md` และ `project-memory/workflows/git-safety-workflow.md` ก่อนเริ่ม

1. ตรวจว่า current diff ยังจำกัดอยู่แค่:
   - `AGENTS.md`
   - `project-memory/workflows/git-safety-workflow.md`
   - `project-memory/04_Agent_Load_Order.md`
2. รัน preflight:
   - `git status --short --branch`
   - `git branch --show-current`
   - `git diff --stat`
   - `git diff --name-only`
3. ถ้ามี dirty/untracked files อื่นนอกจากไฟล์ที่ผู้ใช้อนุมัติไว้ ให้หยุดแล้วถามก่อน
4. ถ้าอยู่บน `main` ให้สร้างและสลับไป `docs/agent-git-safety-workflow` ก่อน commit
5. stage เฉพาะ 3 ไฟล์นี้:
   - `AGENTS.md`
   - `project-memory/workflows/git-safety-workflow.md`
   - `project-memory/04_Agent_Load_Order.md`
6. verify staged files แล้ว commit ด้วย message:
   - `docs(agent): add git safety workflow`
7. push branch `docs/agent-git-safety-workflow`
8. รายงาน commit hash, branch, staged files, และ final git status
9. ห้ามเปิด PR ในคำสั่งนี้
