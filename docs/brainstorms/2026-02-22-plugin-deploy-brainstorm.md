# Plugin Deploy Script — Brainstorm

**Date:** 2026-02-22
**Status:** Ready for planning

## What We're Building

A single shell script (`plugin-deploy.sh`) that automates the manual steps of deploying a Claude Code plugin after its source has been pushed to GitHub. One command replaces the current 7-step manual process (git pull marketplace, copy to cache, edit JSON).

**Usage:** `plugin-deploy.sh <plugin-name>@<marketplace-name>`

**Example:** `plugin-deploy.sh life-agent@life-agent`

## Why This Approach

- **Pain point is real:** Plugin deployment has been a manual slog ~4 of 7 days this week. Steps 3-5 of the current workflow (pull marketplace, copy to cache, hand-edit `installed_plugins.json`) are tedious and error-prone.
- **Simple script wins:** Only 2 active plugins across 3 marketplaces. No need for hooks, watchers, or deploy-all wrappers. YAGNI — add complexity when the need appears.
- **Marketplace-to-cache boundary:** The script starts *after* code is pushed to GitHub. Committing, pushing, and version bumping remain manual development steps. The script handles everything from `git pull` through updated JSON.

## Key Decisions

1. **Scope: marketplace → cache only.** The script does not commit, push, or bump versions. Those are development tasks, not deployment tasks.
2. **Approach: simple shell script (~80 lines).** No frameworks, no Python CLI, no dependencies beyond bash/python3 (for JSON editing).
3. **Versioning: detect by version + SHA.** If the version string hasn't changed but the git SHA has, redeploy anyway. Handles Scott's inconsistent version-bumping habit.
4. **Old cache versions: delete them.** No orphan marking, no rollback support. Scott has never rolled back a plugin. Simpler to just remove the old cache dir.
5. **No `--all` flag (yet).** Can be added in ~10 lines if needed later.

## What the Script Does

1. Parse `<plugin>@<marketplace>` from argument
2. `git pull` the marketplace repo
3. Read version from plugin.json in marketplace source
4. Get git SHA from marketplace repo
5. Compare version + SHA against `installed_plugins.json` — exit early if already current
6. Create new cache dir at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`
7. `cp -R` plugin files from marketplace to cache
8. Delete old cache version directory (if different from new)
9. Update `installed_plugins.json` via python3: installPath, version, lastUpdated, gitCommitSha (preserve scope, installedAt)
10. Print summary: old version → new version, SHA, cache path

## What the Script Does NOT Do

- Bump version in plugin.json (development step)
- Commit or push to GitHub (development step)
- Restart Claude Code (user does this manually)
- Handle multiple plugins at once (add later if needed)

## Open Questions

None — all questions resolved during brainstorm.
