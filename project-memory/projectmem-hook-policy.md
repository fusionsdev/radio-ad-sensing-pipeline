# projectmem Hook Policy

projectmem hooks must not overwrite existing RadioSense hooks.

## Current layout (2026-06-23)

| Hook | Location | Behavior |
|---|---|---|
| pre-commit | `.git/hooks/pre-commit` | projectmem `precheck --level warn \|\| true` — **advisory only** |
| post-commit | `.git/hooks/post-commit` | **Chained:** Understand-Anything → projectmem capture |
| post-merge | `.git/hooks/post-merge` | projectmem merge capture (background, non-fatal) |

`git config core.hooksPath` = `.git/hooks` (default).  
Legacy `.githooks/post-commit` is preserved as reference; active chain lives in `.git/hooks/post-commit`.

## Chain rules

If both projectmem and Understand-Anything need `post-commit`, use a single chain hook:

1. Run existing Understand-Anything logic (mark `.understand-anything/.graph-stale`).
2. Run projectmem `_auto-capture commit` in background.
3. **Never fail the commit** because a post-commit step failed (`exit 0` always).

Pre-commit warnings are advisory unless explicitly configured otherwise. Bypass once: `git commit --no-verify`.

## Reinstall / conflict

If `pjm hooks install` is run again, re-apply the chained `post-commit` from this policy before committing.

Remove projectmem hooks only via: `pjm hooks uninstall` (then restore Understand chain manually if needed).