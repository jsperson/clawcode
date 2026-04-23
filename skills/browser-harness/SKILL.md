---
name: browser-harness
description: Browser automation via browser-harness (CDP direct). Use when user asks
  to "open a website", "browse", "click", "fill form", "take screenshot",
  "check a page", "login to", or needs to interact with web pages that WebFetch
  cannot handle (paywalls, auth walls, bot detection, JS-heavy sites).
allowed-tools: Bash, Read, Edit, Write
metadata:
  clawcode:
    emoji: "🌐"
    os: ["darwin"]
    requires:
      binaries: [browser-harness]
---

# Browser Automation (via browser-harness)

Control Chrome directly via CDP using the `browser-harness` CLI. No MCP server, no extension — just a persistent daemon attached to Chrome with a self-extending Python helpers file.

**Full operating manual lives in the upstream repo — read it before using:**

- `~/source/browser-harness/SKILL.md` — day-to-day usage, tool call shape, gotchas
- `~/source/browser-harness/helpers.py` — all available functions (preloaded into every call)
- `~/source/browser-harness/install.md` — only for first-time install / reconnect

## Invocation shape

```bash
browser-harness <<'PY'
new_tab("https://example.com")
wait_for_load()
print(page_info())
screenshot("/tmp/shot.png")
PY
```

Helpers are pre-imported. The daemon auto-starts. Use `new_tab(url)` for first navigation — `goto(url)` clobbers the user's active tab.

## Self-extension

When you hit a capability gap, **edit `~/source/browser-harness/helpers.py` directly** to add what's missing. The install is editable, so the next `browser-harness` invocation picks up your edit.

This is the intended workflow — the repo README literally says "the agent writes what's missing, mid-task."

**Hygiene:** after meaningful edits to `helpers.py`, `git -C ~/source/browser-harness add -A && git -C ~/source/browser-harness commit -m "add <helper>"` so we have rollback. Don't commit secrets.

## Prerequisites

- Chrome running (local Chrome is dedicated to AI — use it freely)
- Remote debugging enabled (one-time per profile; already set up)
- `browser-harness` on PATH (installed via `uv tool install -e ~/source/browser-harness`)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `daemon didn't come up` | Chrome not running or remote debugging disabled; `open -a "Google Chrome"` then retry |
| `DevToolsActivePort not found` | Open `chrome://inspect/#remote-debugging`, tick the checkbox, click Allow |
| `no close frame received or sent` | Stale daemon; run `browser-harness --doctor`; if needed restart daemon |
| Update banner appears | Run `browser-harness --update -y` yourself, don't ask Scott |
| Completely stuck | `browser-harness --doctor` for full diagnostic |

## Notes

- **Only http/https URLs.** `file://`, `chrome://`, `javascript://` are blocked.
- **Screenshots first.** Use `screenshot()` to see the page; coordinates > selectors for clicks.
- **`http_get(url)` for static pages** — no browser needed for simple fetches.
- **`wait_for_load()` after `goto` / `new_tab`** before interacting.
- **`ensure_real_tab()` if stuck on chrome:// internal pages** or after stale sessions.
