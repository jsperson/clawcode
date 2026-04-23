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

## CRITICAL: NEVER ask Scott to tick chrome://inspect, run --setup, or pick between options

If a browser-harness call fails, **you fix it yourself, silently, then retry**. The complete list of auto-fixes is below. The ONLY time you ask Scott anything is auth walls (login redirects).

**Forbidden messages** (Scott has explicitly said do not send these):
- "Tick the checkbox at chrome://inspect..."
- "Tell me go and I'll retry..."
- "Which option do you want: (1) tick checkbox (2) run --setup..."
- Any variant that asks Scott to do Chrome-setup work

These are solved problems. Scott does not want to see them again.

## Auto-fix table (apply silently, retry)

| Error | Fix |
|---|---|
| `CDP port 9222 isn't listening` | `~/bin/chrome-ai && sleep 2` then retry |
| `Connect call failed` / `Connection refused` on 9222 | `~/bin/chrome-ai && sleep 2` then retry |
| `daemon ... didn't come up` | `~/bin/chrome-ai && sleep 2` then retry |
| `CDP WS handshake failed: HTTP 404` | Retry once silently. If still fails: `~/bin/chrome-ai && sleep 2` then retry |
| `update available: X -> Y` banner | `browser-harness --update -y` (no ask) |
| Auth wall (redirected to login page) | **This is the one case you ask.** Tell Scott to log in in the AI Chrome window. Do NOT type credentials from screenshots. |

The `~/bin/chrome-ai` launcher does everything: kills stale Chrome, starts fresh with `--remote-debugging-port=9222`, writes the correct `BU_CDP_WS` into `~/source/browser-harness/.env`, waits for the port to be live. It is idempotent and safe to run any time.

## Invocation shape

```bash
browser-harness <<'PY'
new_tab("https://example.com")
wait_for_load()
print(page_info())
screenshot("/tmp/shot.png")
PY
```

Helpers are pre-imported. Use `new_tab(url)` for first navigation — `goto(url)` clobbers the user's active tab.

## Self-extension

When you hit a capability gap, edit `~/source/browser-harness/helpers.py` directly. The install is editable; next invocation picks up the edit.

After meaningful edits: `git -C ~/source/browser-harness add -A && git -C ~/source/browser-harness commit -m "add <helper>"`. Don't commit secrets.

## Full upstream docs (read when you need depth)

- `~/source/browser-harness/SKILL.md` — day-to-day usage, gotchas
- `~/source/browser-harness/helpers.py` — available functions

## Prerequisites (already in place — don't re-setup)

- Chrome dedicated to AI on this machine
- `browser-harness` installed via `uv tool install -e ~/source/browser-harness`
- `~/bin/chrome-ai` launcher + `com.clawcode.chrome-ai` LaunchAgent auto-start Chrome on login
- Dedicated profile at `~/.chrome-ai-profile` (session cookies persist across Chrome restarts)

## Notes

- **Only http/https URLs.** `file://`, `chrome://`, `javascript://` are blocked.
- **Screenshots first.** Use `screenshot()` to see the page; coordinates > selectors for clicks.
- **`http_get(url)` for static pages** — no browser needed for simple fetches.
- **`wait_for_load()` after `goto` / `new_tab`** before interacting.
- **`ensure_real_tab()` if stuck on chrome:// internal pages** or after stale sessions.
