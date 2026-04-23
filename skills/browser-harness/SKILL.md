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

**Full operating manual lives in the upstream repo — read when you need depth:**

- `~/source/browser-harness/SKILL.md` — day-to-day usage, tool call shape, gotchas
- `~/source/browser-harness/helpers.py` — all available functions (preloaded into every call)

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

When you hit a capability gap, **edit `~/source/browser-harness/helpers.py` directly** to add what's missing. The install is editable, so the next `browser-harness` invocation picks up your edit.

After meaningful edits: `git -C ~/source/browser-harness add -A && git -C ~/source/browser-harness commit -m "add <helper>"`. Don't commit secrets.

## Auto-remediation — handle failures yourself, don't ask

**These are known failure modes with canonical fixes. Apply them silently, then retry. Do NOT ask the user which option to pick.**

### "CDP port 9222 isn't listening" / "Connect call failed" / daemon won't come up

**Fix:** Chrome isn't running (or isn't running with debug flags). Run the launcher, wait briefly, retry once:

```bash
~/bin/chrome-ai
sleep 2
# retry the original browser-harness call
```

That's it. The launcher handles killing any stale Chrome, starting a fresh one with `--remote-debugging-port=9222`, writing the correct `BU_CDP_WS` to `~/source/browser-harness/.env`, and waiting for the port to be live.

**Do not:**
- Tell the user to open `chrome://inspect`
- Run `browser-harness --setup`
- Ask which option they want
- Offer fallbacks — there is one fix, apply it

### "CDP WS handshake failed: server rejected WebSocket connection: HTTP 404"

**Fix:** First-invocation race after Chrome start. Retry the exact same `browser-harness` call once. If it still fails, fall through to the launcher remediation above.

### Auth wall (redirected to login page)

**Fix:** This is the one case you DO ask the user. Tell them they need to log in in the AI Chrome window (it's visible on screen). Do NOT type credentials from screenshots. After the user confirms login, retry.

### Update banner at top of output

**Fix:** Run `browser-harness --update -y` yourself. Don't ask.

## Prerequisites (already in place)

- Chrome dedicated to AI on this machine — use it freely
- `browser-harness` installed via `uv tool install -e ~/source/browser-harness`
- `~/bin/chrome-ai` launcher + `com.clawcode.chrome-ai` LaunchAgent auto-start Chrome on login
- Dedicated profile at `~/.chrome-ai-profile` (session cookies persist across restarts)

## Notes

- **Only http/https URLs.** `file://`, `chrome://`, `javascript://` are blocked.
- **Screenshots first.** Use `screenshot()` to see the page; coordinates > selectors for clicks.
- **`http_get(url)` for static pages** — no browser needed for simple fetches.
- **`wait_for_load()` after `goto` / `new_tab`** before interacting.
- **`ensure_real_tab()` if stuck on chrome:// internal pages** or after stale sessions.
