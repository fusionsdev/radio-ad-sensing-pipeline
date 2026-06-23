# projectmem - radio-ad-sensing-pipeline

_Last updated: 2026-06-23_

## Project purpose
Local 24/7 radio ad-sensing pipeline

## Recent issues
- [DONE] #legacy_628c Legacy issue: fix(ingestor): skip reconnect_at_eof on HLS streams -> fix(ingestor): skip reconnect_at_eof on HLS streams (fixed)
- [DONE] #legacy_5e81 Legacy issue: fix(keywords): expand loan coverage, word-boundary match, observability -> fix(keywords): expand loan coverage, word-boundary match, observability (fixed)
- [DONE] #legacy_0859 Legacy issue: chore(wip): checkpoint working tree before code-review fixes -> chore(wip): checkpoint working tree before code-review fixes (fixed)
- [OPEN] #0007 harvest dashboard test expects href=/radio-harvest self-link that current control panel no longer renders [tests/test_harvest_dashboard.py:255] (open)
- [OPEN] #0006 consumer loan gate does not persist cash advance keyword when transcript contains loan intent [tests/test_consumer_personal_loan_gating.py:123] (open)
- [OPEN] #0005 test_config expects asr_compute_type int8_float16 but repository settings load float16 [tests/test_config.py:34] (open)
- [OPEN] #0004 audit_keyword_hits_verticals flags personal loan as polluted and deletes two rows instead of one [tests/test_audit_keyword_hits_verticals.py:58] (open)
- [OPEN] #0003 extract_slug_name parses Justia numeric path segment instead of mark slug filename [scripts/discover_justia_names_via_apify.py:39] (open)
- [OPEN] #0002 extract_serial_from_url fails to parse Justia trademark URLs with serial in filename [scripts/discover_justia_names_via_apify.py:28] (open)
- [OPEN] #0001 test_apify_name_collector.py::test_load_queries expects 150 Apify queries but current fixture loads 1200 [tests/test_apify_name_collector.py:14] (open)

## Decisions
- No decisions logged yet.

## Notes
- feat(keywords): v2 phrase dictionary, scorecard, and review inbox
- chore(docs): move handoff plans to .devin/plans
- vault backup: 2026-06-23 07:17:43
- vault backup: 2026-06-23 07:18:52
- vault backup: 2026-06-23 07:28:11
- vault backup: 2026-06-23 07:38:15
- vault backup: 2026-06-23 07:48:17
- vault backup: 2026-06-23 07:58:20
- vault backup: 2026-06-23 08:08:22
- vault backup: 2026-06-23 08:18:24

## Key files
- `.agents/skills/caveman/SKILL.md`
- `.agents/skills/design-an-interface/SKILL.md`
- `.agents/skills/diagnose/SKILL.md`
- `.agents/skills/diagnose/scripts/hitl-loop.template.sh`
- `.agents/skills/edit-article/SKILL.md`
- `.agents/skills/git-guardrails-claude-code/SKILL.md`
- `.agents/skills/git-guardrails-claude-code/scripts/block-dangerous-git.sh`
- `.agents/skills/grill-me/SKILL.md`
- `.agents/skills/grill-with-docs/ADR-FORMAT.md`
- `.agents/skills/grill-with-docs/CONTEXT-FORMAT.md`
- `.agents/skills/grill-with-docs/SKILL.md`
- `.agents/skills/handoff/SKILL.md`
- `.agents/skills/hermes-dispatch/PROMPTS.md`
- `.agents/skills/hermes-dispatch/SKILL.md`
- `.agents/skills/hermes-dispatch/scripts/hermes-review.ps1`
- `.agents/skills/hermes-dispatch/scripts/hermes-review.sh`
- `.agents/skills/improve-codebase-architecture/DEEPENING.md`
- `.agents/skills/improve-codebase-architecture/HTML-REPORT.md`
- `.agents/skills/improve-codebase-architecture/INTERFACE-DESIGN.md`
- `.agents/skills/improve-codebase-architecture/LANGUAGE.md`

## Open questions
- None logged yet.
