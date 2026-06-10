# สถานะ pipeline

อ่าน `.agents/skills/pipeline-ops/SKILL.md` แล้วเช็คสถานะให้ operator (ภาษาไทย สั้น)

1. รัน `.\scripts\pipeline-status.ps1` และ `docker compose ps`
2. ตอบแบบ: บรรทัดเดียว OK/DEGRADED + bullet สำคัญ + คำแนะนำ 1 ข้อถ้ามีปัญหา
3. อย่าอ่าน `data/pipeline.db` จาก Windows host ตอน Docker ingest อยู่
