# Git Safety Workflow For RadioSense Agent

Use this workflow before any file, Git, branch, stash, PR, or Linear change in `radio-ad-sensing-pipeline`.

## Purpose

Keep Git work safe and auditable. Do not mix runtime code, memory files, generated artifacts, tool cache, or branch history accidentally.

## Hard Rules

Do not do any of the following unless the user explicitly asks for it:

- `git reset --hard`
- `git clean`
- `git stash pop`
- merge a branch without auditing it first
- commit from a dirty worktree without explaining the dirt
- commit memory files together with runtime code
- commit generated exports, reports, or backups without approval
- delete untracked files
- switch branches while the worktree is dirty without reporting first
- restart or deploy Docker/live services without explicit instruction

## Before Any Work

Run these commands first:

```powershell
git status --short --branch
git branch --show-current
git diff --stat
git diff --cached --stat
```

Then report:

```md
## Git Preflight

Current branch:
...

Tracked dirty files:
...

Staged files:
...

Untracked files:
...

Risk:
clean / dirty / blocked

Decision:
continue / ask user / create new branch / stash specific files
```

If there are dirty files unrelated to the task, stop and ask first.

## Branch Rules

One branch should serve one intent only:

| Work | Branch |
|---|---|
| runtime bug fix | `fix/...` |
| dashboard | `fix/dashboard-...` |
| memory/docs | `chore/memory-...` |
| audit script | `feat/audit-...` |
| experiment | `exp/...` |
| integration cleanup | `chore/integration-...` |

Do not mix:

- runtime code + project memory
- source code + exports/reports
- dashboard + unrelated worker changes
- memory restore + runtime fixes
- tool/cache dirs + source changes

## Memory Files Policy

Keep memory work on a dedicated branch whenever possible.

Allowed in memory branches:

- `.projectmem/**`
- `project-memory/**/*.md`
- `project-memory/.gitignore`
- `.gitkeep`

Do not commit unless explicitly approved:

- `project-memory/.obsidian/workspace.json`
- `project-memory/.obsidian/plugins/**`
- `project-memory/.smart-env/**`
- JSON metric snapshots
- local tool dirs

If projectmem auto-updates after a merge, commit it separately:

```powershell
git add .projectmem/events.jsonl .projectmem/summary.md
git commit -m "chore(memory): capture project memory update"
```

## Blocked Paths

Before commit, inspect staged files:

```powershell
git diff --cached --name-only
```

If any of these paths are staged, stop and report:

- `.claude/`
- `.serena/`
- `project-memory/.obsidian/workspace.json`
- `project-memory/.obsidian/plugins/`
- `project-memory/.smart-env/`
- `exports/`
- `reports/`
- `backups/`
- `*.bak.*`
- `*.db`
- `*.sqlite`
- `*.sqlite3`

Unless the user explicitly approves, do not proceed.

## Stash Rules

Do not use:

```powershell
git stash
git stash pop
```

Use path-specific stash only, with a message:

```powershell
git stash push -m "temp: explain what is being preserved" -- path/to/file
```

Before applying a stash, inspect it:

```powershell
git stash list --max-count=10
git stash show --stat stash@{N}
git stash show --name-only --include-untracked stash@{N}
```

Use `git stash apply` only. Never use `pop`.

## Commit Rules

Before commit:

```powershell
git status --short --branch
git diff --cached --stat
git diff --cached --name-only
```

Keep each commit to one topic.

Good:

```text
fix(ingestor): skip reconnect at EOF for HLS streams
chore(memory): restore project memory vault
test(dashboard): cover partial auth env state
```

Bad:

```text
update stuff
fix all
vault backup
wip
```

## Test Rules

For runtime code changes:

```powershell
.venv\Scripts\pytest -q
```

If focused tests exist, run them before the full suite.

For memory/docs-only changes:

- full `pytest` is not required
- report that the change was docs/memory-only

## PR Rules

Important work should go through a PR:

```text
branch -> tests -> push -> PR draft -> review -> ready -> squash merge -> pull main
```

After merge:

```powershell
git switch main
git pull --ff-only
git status --short --branch
.venv\Scripts\pytest -q
```

Then start the next branch.

## Conflict Rules

If a cherry-pick or merge conflict appears:

1. Stop immediately.
2. Do not guess.
3. Run:

```powershell
git status --short --branch
git diff --name-only --diff-filter=U
git diff -- <conflict-file>
```

4. Report:

```md
Conflict files:
...

Conflict type:
...

Recommended resolution:
...

Need user decision:
yes/no
```

Do not continue until the conflict is resolved and tests pass.

## Linear / External Tools

Do not send internal repo details to external tools if policy or tool rules block it.

If Linear must be updated, use a sanitized summary only:

- no commit IDs
- no branch names
- no deep file paths
- no stash details
- no secrets or config details

If a tool is blocked, ask the user to copy the sanitized text manually.

## Final Report Format

End every task with:

```md
## Summary
...

## Files Changed
...

## Commands Run
...

## Test Results
...

## Memory Updated
...

## Risks / Follow-ups
...
```

## Default Behavior

If in doubt:

- stop
- report the current state
- ask for approval

Do not guess about Git.
Do not clean the repo.
Do not reset.
Do not pop stash.
Do not merge a branch wholesale.
