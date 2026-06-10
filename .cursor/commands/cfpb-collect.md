# รัน CFPB collect

อ่าน `plan/handoff-cfpb-20260611.md` + `docs/cfpb-complaint-collector.md`

1. รัน `.\scripts\run-cfpb-collector.ps1 -Docker` (หรือ host ถ้า Docker ไม่ up)
2. สรุปผลภาษาไทย: records inserted, entities, candidates
3. ถาม operator ก่อนถ้า worker backlog สูงมาก (SQLite contention)
