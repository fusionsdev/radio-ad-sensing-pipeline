# Obsidian Git Setup

Vault: `project-memory/` inside `radio-ad-sensing-pipeline` git repo.

## Installed

- Plugin: **obsidian-git** v2.38.5
- Path: `.obsidian/plugins/obsidian-git/`

## One-time in Obsidian UI

1. Open vault: `H:\DEV\projects\radio-ad-sensing-pipeline\project-memory`
2. **Settings → Community plugins → Turn on community plugins** (disable Restricted mode if prompted)
3. Confirm **obsidian-git** is enabled
4. **Settings → Obsidian Git** — verify:
   - **Custom base path (Git repository path):** `..` (repo root is parent of vault)
   - **Custom Git directory path:** *(empty — default `.git`)*
   - **Git executable path:** `C:\Program Files\Git\cmd\git.exe` (if “git not found”)
5. **Restart Obsidian** after changing git path settings
6. Command palette → `Obsidian Git: Commit-and-sync` (test once)

## Auto backup (preconfigured)

| Setting | Value |
|---|---|
| Auto commit interval | 10 min |
| Auto pull interval | 10 min |
| Auto push interval | 20 min |
| Pull on startup | on |

Settings file: `.obsidian/plugins/obsidian-git/data.json` (restored if UI settings disappear).

## Settings disappeared?

1. Confirm plugin enabled: **Settings → Community plugins → Git** (obsidian-git)
2. **Restart Obsidian** (required after path changes)
3. **Settings → Git** — re-check:
   - **Custom base path:** `..`
   - **Custom Git directory path:** *(empty)*
   - **Git executable path:** `C:\Program Files\Git\cmd\git.exe` *(device-local — not in `data.json`)*
4. Command palette → `Obsidian Git: Open source control view` — should show branch `main`
5. Test: `Obsidian Git: Commit-and-sync`

If **“git not found”**: set executable path above, restart Obsidian.

## Related

- [[02_Operating_Policy]]
- [[Decisions/Memory OS Phase 1]]