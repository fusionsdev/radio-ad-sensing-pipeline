# Git safety PR

อ่าน `AGENTS.md` และ `project-memory/workflows/git-safety-workflow.md` ก่อนเริ่ม

1. ตรวจว่า branch คือ `docs/agent-git-safety-workflow`
2. ตรวจว่า current diff ยังจำกัดอยู่แค่:
   - `AGENTS.md`
   - `project-memory/workflows/git-safety-workflow.md`
   - `project-memory/04_Agent_Load_Order.md`
3. ถ้าไม่ตรง ให้หยุดแล้วถามก่อน
4. เปิด PR จาก `docs/agent-git-safety-workflow` ไป `main`
5. ใช้ title:
   - `Add agent Git safety workflow`
6. ใช้ body ตาม policy:
   - summary
   - verification ว่า tests not run; docs-only
   - scope ว่าไม่มี runtime code change
7. รายงาน PR URL
