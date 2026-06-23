# Linear → Oracle → Agent Workflow

Use Linear as the source of truth for task tracking, project-memory as repo memory, and Oracle/ChatGPT as an external reviewer only when useful.

## Core Rules

- Linear issue is the task source.
- Repo + project-memory are the technical source of truth.
- Oracle/ChatGPT is advisory, not authoritative.
- Follow `project-memory/workflows/git-safety-workflow.md` before any file, Git, branch, stash, PR, or Linear action.
- Branch creation and switching are governed by the Git safety workflow. If starting from `main`, create a dedicated branch before edits.
- Do not send unnecessary private repo data externally.
- Do not paste huge files into Oracle.
- Ask narrow Oracle questions with selected files/diffs only.
- Do not commit or push until local checks pass.

## External Tool Sanitization

Any Linear comment, status update, or external-tool update must be sanitized.

Do not include:

- commit IDs
- branch names
- deep file paths
- stash details
- secrets
- config values
- credentials
- internal logs
- raw diffs
- large repo excerpts
- private operational details

Allowed Linear update content:

- task goal
- high-level status
- high-level risk
- test status in broad terms
- next action
- blocker summary without sensitive details

If an external-tool update is blocked by policy, do not retry or workaround. Provide a sanitized message for the user to copy manually.

## Oracle Consultation Triggers

Consult Oracle only when useful. Required or strongly recommended for:

- architecture changes
- cross-cutting refactors
- security-sensitive changes
- auth, secrets, token, or external API handling
- runtime pipeline behavior changes
- watchdog, worker, ingestor, classifier, dashboard control, or alerter behavior changes
- unexplained test failures
- merge/cherry-pick conflicts in risky files
- changes that may affect live pipeline stability
- PR final review for medium/high-risk work

Oracle is usually unnecessary for:

- docs-only edits
- typo fixes
- narrow test-only changes
- formatting-only changes
- mechanical rename with no behavior change

## Oracle Unavailable / Skipped

If Oracle is unavailable, blocked, unnecessary, or would require sending too much context:

1. Continue with local repo reasoning.
2. Note clearly:
   - `Oracle skipped`
   - reason: unavailable / unnecessary / too much context / policy block
3. Proceed with the normal Git safety, branch, test, and PR workflow.
4. Do not stall unless the task genuinely requires external review.

## Workflow

1. Read the Linear issue.
2. Restate:
   - goal
   - scope
   - likely files or areas
   - risks
   - acceptance criteria
3. Run Git safety preflight:
   - `git status --short --branch`
   - `git diff --stat`
   - `git diff --cached --stat`
4. Read project-memory and relevant repo files.
5. Decide whether Oracle is required using the trigger list.
6. If Oracle is used:
   - summarize the issue
   - attach only focused files/diff
   - ask for bug/regression/security/test review
   - treat response as advisory only
7. Save only a sanitized Oracle Consultation summary to Linear if allowed.
8. Implement on a dedicated branch governed by the Git safety workflow.
9. Run focused tests, then full tests if runtime code changed.
10. Open PR when ready.
11. Update Linear with sanitized status:
   - high-level progress
   - PR state
   - broad test result
   - high-level risks
   - next action

## Linear Issue Template

```md
## Goal
...

## Scope
...

## Constraints
- Consumer personal loans only
- Do not touch live services unless explicitly approved
- Follow Git safety workflow
- Oracle is advisory only
- Linear updates must be sanitized

## Files / Areas
...

## Acceptance Criteria
- ...
- Tests pass
- PR opened or merged

## Oracle Required?
Yes / No

## Notes
...
```

## Oracle Consultation Format

Keep this detailed locally or in project-memory. If posting to Linear, sanitize it first.

```md
## Oracle Consultation

Question:
...

Files/diff sent:
...

Oracle summary:
...

Accepted:
...

Rejected:
...

Reasoning:
...

Implementation decision:
...
```

## Sanitized Linear Update Format

```md
## Status
On track / At risk / Blocked

## Progress
- ...

## Verification
- Local checks passed / pending / failed

## Risk
- High-level risk only

## Next Action
- ...
```

## Final Agent Report

```md
## Summary
...

## Linear Updated
yes/no
If no, reason:
...

## Oracle Used
yes/no
If no, reason:
...

## Files Changed
...

## Commands Run
...

## Test Results
...

## Risks / Follow-ups
...
```
