---
title: "feat: Plugin Deploy Script"
type: feat
status: completed
date: 2026-02-22
brainstorm: docs/brainstorms/2026-02-22-plugin-deploy-brainstorm.md
---

# feat: Plugin Deploy Script

Automate the manual marketplace-to-cache plugin deployment steps into a single command. Replaces the current 7-step process (git pull, cp -R, hand-edit JSON) that's been a pain point ~4 of 7 days this week.

## Acceptance Criteria

- [x] `plugin-deploy.sh life-agent@life-agent` pulls marketplace, copies to cache, updates JSON
- [x] Same-version + same-SHA combo exits with "already current"
- [x] Same-version + different-SHA correctly redeploys (handles no-version-bump case)
- [x] Missing plugin key in JSON creates a new entry (first-install support)
- [x] Old cache directory deleted when version changes
- [x] Summary printed: old version/SHA → new version/SHA, cache path
- [x] Prints "Restart Claude Code to pick up changes." at end
- [x] Pre-flight errors are clear: bad argument format, missing marketplace dir, missing plugin dir, git pull failure

## Implementation

### File: `~/source/clawcode/scripts/plugin-deploy.sh`

Follow existing script conventions:
- `#!/usr/bin/env bash` + `set -euo pipefail`
- Header: `# plugin-deploy.sh — Deploy a Claude Code plugin from marketplace to cache`
- Usage block with examples
- Errors to stderr, progress to stdout

### Script Flow

```
1. PARSE argument: split on "@" → PLUGIN, MARKETPLACE
   - Validate format: must contain exactly one "@"
   - Print usage and exit 1 if bad

2. VALIDATE paths:
   - MARKETPLACE_DIR="$HOME/.claude/plugins/marketplaces/$MARKETPLACE"
   - Check -d "$MARKETPLACE_DIR" → exit "marketplace '$MARKETPLACE' not found"
   - PLUGIN_JSON="$MARKETPLACE_DIR/plugins/$PLUGIN/.claude-plugin/plugin.json"

3. GIT PULL marketplace:
   - git -C "$MARKETPLACE_DIR" pull
   - Exit on failure with clear message (network, auth, merge conflict)

4. VALIDATE plugin exists:
   - Check -f "$PLUGIN_JSON" → exit "plugin '$PLUGIN' not found in marketplace"

5. READ new state:
   - NEW_VERSION: python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$PLUGIN_JSON"
   - NEW_SHA: git -C "$MARKETPLACE_DIR" rev-parse --short HEAD

6. READ old state from installed_plugins.json:
   - INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
   - Use python3 to read old version + SHA for key "$PLUGIN@$MARKETPLACE"
   - If key missing: OLD_VERSION="(none)", OLD_SHA="(none)"

7. COMPARE: if OLD_VERSION == NEW_VERSION && OLD_SHA == NEW_SHA → print "already current" and exit 0

8. DEPLOY to cache:
   - CACHE_DIR="$HOME/.claude/plugins/cache/$MARKETPLACE/$PLUGIN/$NEW_VERSION"
   - rm -rf "$CACHE_DIR" (guard against stale partial copy)
   - mkdir -p "$CACHE_DIR"
   - cp -R "$MARKETPLACE_DIR/plugins/$PLUGIN/." "$CACHE_DIR/"

9. CLEAN old cache (if version changed):
   - OLD_CACHE_DIR="$HOME/.claude/plugins/cache/$MARKETPLACE/$PLUGIN/$OLD_VERSION"
   - If OLD_VERSION != NEW_VERSION && OLD_VERSION != "(none)" && -d "$OLD_CACHE_DIR":
     rm -rf "$OLD_CACHE_DIR"

10. UPDATE installed_plugins.json:
    - Python3 inline script:
      - Load JSON
      - KEY = "$PLUGIN@$MARKETPLACE"
      - If key missing: create with [{"scope": "user", "installedAt": now_iso}]
      - Update [KEY][0]: installPath, version, lastUpdated, gitCommitSha
      - Write JSON (indent=2)

11. PRINT summary:
    - "$PLUGIN@$MARKETPLACE: $OLD_VERSION ($OLD_SHA) → $NEW_VERSION ($NEW_SHA)"
    - "Cache: $CACHE_DIR"
    - "Restart Claude Code to pick up changes."
```

### Exit Codes

- `0` — deployed successfully OR already current
- `1` — any error (bad args, missing dirs, git failure, JSON failure)

### Dependencies

- `bash`, `git`, `python3` (all present on macOS)
- No new packages or tools

## Context

### Key Paths

| Path | Purpose |
|------|---------|
| `~/.claude/plugins/marketplaces/<mkt>/` | Git-cloned marketplace repos |
| `~/.claude/plugins/marketplaces/<mkt>/plugins/<plugin>/` | Plugin source in marketplace |
| `~/.claude/plugins/cache/<mkt>/<plugin>/<version>/` | Deployed cache (what Claude Code reads) |
| `~/.claude/plugins/installed_plugins.json` | Metadata telling Claude Code what's installed |

### installed_plugins.json Structure

```json
{
  "version": 2,
  "plugins": {
    "life-agent@life-agent": [
      {
        "scope": "user",
        "installPath": "/Users/jsperson/.claude/plugins/cache/life-agent/life-agent/0.3.5",
        "version": "0.3.5",
        "installedAt": "2026-02-11T...",
        "lastUpdated": "2026-02-15T...",
        "gitCommitSha": "abc1234"
      }
    ]
  }
}
```

Each plugin key maps to an array. Always one entry (index 0). Update in place; preserve `scope` and `installedAt`.

## Verification

1. Run `plugin-deploy.sh life-agent@life-agent` with no pending changes → should report "already current"
2. Manually bump life-agent version in source, push, run again → new cache dir, updated JSON, summary printed
3. Push code without version bump → same version dir but SHA-triggered redeploy
4. Bad argument (`plugin-deploy.sh foo`) → usage message, exit 1
5. Wrong marketplace name → clear "not found" error
6. After verification, deploy script to `~/clawcode/scripts/`

## References

- Brainstorm: `docs/brainstorms/2026-02-22-plugin-deploy-brainstorm.md`
- Script conventions: follows patterns from `scripts/gmail-send-attachment.sh`, `scripts/icalpal-query.sh`
- Memory: Plugin deploy workflow documented in `memory/topics/development.md`
