# Agent Teams + Codex Command Set

Tags: `#codex`

คู่มือนี้ตั้งใจให้ใช้ได้ 2 แบบ:

1. เป็นเทมเพลตกลางสำหรับทุกโปรเจกต์
2. เป็นค่าเริ่มต้นสำหรับโปรเจกต์ `radio-ad-sensing-pipeline`

## เป้าหมาย

- ให้ `Oracle` เป็นคนคุมภาพรวม
- ให้ `Codex` ทำงานเป็นทีมย่อยผ่าน MCP / Agent Teams AI
- ลดการใช้โมเดล GPT เกินจำเป็น
- แยกงานให้ชัด: คิด, รีวิว, ลงมือ, สำรอง

## บทบาทในทีม

### 1. Oracle

- ตำแหน่ง: `Lead planner`
- หน้าที่:
  - รับโจทย์จากคน
  - แปลงเป็นแผน
  - แตกงานให้ทีมย่อย
  - ตัดสินใจเรื่อง trade-off
  - รวมผลก่อนส่งกลับ

### 2. Reviewer

- ตำแหน่ง: `reviewer`
- หน้าที่:
  - ตรวจ logic
  - ตรวจ regression
  - มองหาช่องโหว่ของแผน
  - ชี้จุดเสี่ยงสั้นๆ

### 3. Worker

- ตำแหน่ง: `worker` หรือ `developer`
- หน้าที่:
  - ลงมือแก้ไฟล์
  - เขียนโค้ด
  - ทำ refactor ตามแผน
  - ส่งผลลัพธ์กลับให้ lead

### 4. Reasoner

- ตำแหน่ง: `reasoner`
- หน้าที่:
  - คิดโจทย์ยาก
  - ช่วยแตกปัญหาที่มีหลายทางเลือก
  - เตรียม fallback plan

### 5. Fallback

- ตำแหน่ง: `fallback`
- หน้าที่:
  - รับงานง่ายๆ หรือกู้สถานการณ์
  - ใช้เมื่อ lead / worker หลักติด
  - ทำ cleanup, summary, or sanity checks

## คำสั่ง Slash

ใช้เป็น command set ภายในทีม หรือเป็น mental model ตอนสั่งงานผ่าน UI / MCP

- `/oracle` = ให้ lead คิดแผนและแจกงาน
- `/review` = ส่งให้ reviewer ตรวจ
- `/worker` = ให้คนลงมือทำ
- `/reason` = ให้ reasoner แตกโจทย์
- `/fallback` = ส่งงานรองหรือกู้สถานการณ์
- `/status` = สรุปสถานะงานปัจจุบัน
- `/handoff` = ส่งต่อบริบทให้ทีมอื่น
- `/pid <PID>` = ผูกงานกับ process ที่ระบุ ถ้าระบบรองรับ
- `/team create` = สร้างทีมใหม่
- `/team launch` = เปิดทีมให้ทำงาน
- `/task create` = สร้าง task ให้ lead แจกต่อ
- `/task review` = สั่งตรวจงาน

## การเลือกโมเดลแบบสมดุล

หลักคิด:

- ใช้โมเดลเก่งที่สุดกับงานที่คุ้มจริง
- อย่าให้ทุกตัวเป็นโมเดลแพงสุด
- งานที่เดาได้ให้ใช้โมเดลเบา
- งานที่ต้องตัดสินใจให้ใช้ Oracle หรือ lead ที่แรงกว่า

### ค่าเริ่มต้นแนะนำ

- `Oracle / Lead`: `ChatGPT` หรือ `Claude Max`
- `Reviewer`: `Claude Max` หรือ `DeepSeek`
- `Worker`: `DeepSeek` หรือโมเดลที่คุ้มต้นทุนกว่า
- `Reasoner`: `Claude Max` ถ้าต้องใช้เหตุผลหนัก
- `Fallback`: โมเดลเบา หรือ `DeepSeek`

### ถ้าจะบาลานซ์ไม่เน้น GPT เยอะ

- ใช้ `Claude Max` เป็น lead หลัก
- ใช้ `DeepSeek` เป็น worker / fallback
- เก็บ `ChatGPT` ไว้เป็น Oracle สำหรับ planning และ final check

## เทมเพลตทีมมาตรฐาน

```json
[
  {
    "name": "oracle",
    "role": "lead",
    "providerId": "chatgpt"
  },
  {
    "name": "reviewer",
    "role": "reviewer",
    "providerId": "claude"
  },
  {
    "name": "worker",
    "role": "developer",
    "providerId": "deepseek"
  },
  {
    "name": "reasoner",
    "role": "reasoner",
    "providerId": "claude"
  },
  {
    "name": "fallback",
    "role": "support",
    "providerId": "deepseek"
  }
]
```

## เวอร์ชันระบุ PID

ใช้เมื่อคุณเปิด Agent Teams AI เอง แล้วอยากให้ Codex ผูกกับ process นั้น

```text
/pid <PID>
/oracle สร้างทีม
/worker ทำงาน
/review ตรวจผล
```

ตัวอย่าง:

```text
/pid 55084
/oracle สร้างทีมสำหรับงานนี้
/worker แยกงานเป็น 3 ขั้น
/review เช็กผลลัพธ์ก่อนปิดงาน
```

## เวอร์ชันให้ Oracle คิดทีมเอง

ใช้เมื่อคุณแค่อยากบอกโจทย์เดียว แล้วให้ Oracle จัดทีมและแจกงานเอง

```text
/oracle
โจทย์: <ใส่ปัญหา>
เงื่อนไข:
- ต้องใช้โมเดลให้คุ้ม
- อย่าเน้น GPT มากเกินไป
- ต้องมี reviewer, worker, reasoner, fallback
- ถ้าต้องใช้ process ให้ระบุ PID
```

## Project override: radio-ad-sensing-pipeline

สำหรับ repo นี้ ให้จำค่าเริ่มต้นแบบนี้:

- Oracle = คุมแผนและสรุป
- Reviewer = จับ regression / risk
- Worker = แก้โค้ดและทำงานตาม plan
- Reasoner = ช่วยงานที่ซับซ้อน เช่น architecture / data flow
- Fallback = งานกู้สถานการณ์, cleanup, summary

ข้อจำกัดสำคัญ:

- โฟกัสเฉพาะ consumer personal loans
- อย่าขยาย scope ไปยัง tax relief, insurance, debt settlement, car dealers, windows/home improvement, supplements, หรือ generic bank ads เว้นแต่ผู้ใช้ขอ

## MCP workflow ที่แนะนำ

1. คนสั่งงานเข้า `Oracle`
2. `Oracle` สร้าง team หรือ task ผ่าน MCP
3. `Lead` แจกงานให้ `reviewer`, `worker`, `reasoner`, `fallback`
4. `Lead` รวบรวมผล
5. `Oracle` สรุปและตอบกลับคน

## ตัวอย่าง prompt สั้น

### สร้างทีม

```text
/oracle สร้างทีมให้สมดุลสำหรับงานนี้ โดยใช้ Claude Max, ChatGPT, และ DeepSeek แบบไม่เน้น GPT เยอะ
```

### ส่งงาน

```text
/worker แก้ส่วน ingest ให้รองรับกรณีล้มเหลวแบบ retry
```

### ตรวจงาน

```text
/review เช็กว่ามี side effect กับ queue หรือ database concurrency ไหม
```

### คิดแผน

```text
/reason แตกงานนี้เป็นขั้นตอน พร้อมระบุความเสี่ยง
```

## Notes

- ถ้าใช้ในหลายโปรเจกต์ ให้คัดเฉพาะส่วน `Slash Commands`, `Team Roles`, และ `Balanced Model Defaults`
- ถ้าใช้กับทีมนี้ ให้ใช้ส่วน `Project override`
- ถ้าระบบ Agent Teams AI รองรับ PID binding จริง ให้ใส่ PID ก่อนสั่งสร้างทีม
