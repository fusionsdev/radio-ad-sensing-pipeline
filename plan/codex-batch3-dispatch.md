# Codex CLI Batch 3 — Parallel Dispatch

Started via `codex exec` (non-interactive, workspace-write / read-only).

## Commands pattern

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
$p = Get-Content plan\codex-batch3-wpN-prompt.txt -Raw
codex exec -C $PWD -s workspace-write --dangerously-bypass-approvals-and-sandbox `
  -m gpt-5.4 -o plan\codex-out-wpN.md $p
```

## Jobs — ✅ ทั้งหมดเสร็จ (stdin pipe pattern)

| Job | Model | ผล | Output |
|---|---|---|---|
| WP-5 fix | gpt-5.4 | ✅ ship, 69 pytest | `codex-out-wp5.md`, `wp5-report.md` |
| WP-8 review | gpt-5.4 | 🔧 fix-then-ship | `codex-out-wp8.md` |
| WP-6 alerter | gpt-5.4-mini | ✅ ship, 74 pytest | `codex-out-wp6.md`, `wp6-report.md` |
| WP-10b metrics | gpt-5.4-mini | ✅ ship | `codex-out-wp10b.md`, `wp10b-report.md` |

**รวม:** `pytest` **74/74 passed**

### คำสั่งที่ใช้ (copy ได้)

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
Get-Content plan\codex-batch3-wp5-prompt.txt -Raw |
  codex exec -C $PWD -s workspace-write --dangerously-bypass-approvals-and-sandbox `
    -m gpt-5.4 -o plan\codex-out-wp5.md -
```

> ใช้ `-` รับ prompt จาก stdin — อย่าส่ง multiline เป็น argument ตรงๆ (รอบแรกค้าง)

## After completion

```powershell
.venv\Scripts\pytest -q
git status
```

Merge reports into `plan/opus-review-plan-6165b3.md` checklist.
