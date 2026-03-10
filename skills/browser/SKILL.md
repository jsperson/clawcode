---
name: browser
description: Browser automation — navigate, click, type, screenshot, evaluate JS.
  Use when user asks to "open a website", "browse", "click", "fill form",
  "take screenshot", "check a page", "login to", or needs to interact with
  web pages that WebFetch cannot handle (paywalls, auth walls, bot detection).
allowed-tools: mcp__browser__*
metadata:
  clawcode:
    emoji: "🌐"
    os: ["darwin"]
    requires:
      mcp_servers: [browser]
---

# Browser Automation (via OpenClaw)

Control Scott's real Chrome browser through MCP tools. Uses OpenClaw's CDP relay + Chrome extension for reliable automation with persistent sessions (cookies, logins preserved).

## Prerequisites

- **OpenClaw gateway** must be running: `openclaw browser start`
- **Chrome extension** "OpenClaw Browser Relay" must be installed and connected
- Check status: `browser_status`

## Core Workflow

1. **Navigate** → `browser_navigate` (returns accessibility snapshot with refs)
2. **Read** → `browser_snapshot` (re-snapshot if refs go stale)
3. **Interact** → `browser_click`, `browser_type`, `browser_press`
4. **Verify** → `browser_screenshot` (visual check) or `browser_snapshot` (text check)
5. **Wait** → `browser_wait` (if page is loading or updating async)

## Tool Reference

| Tool | Purpose |
|------|---------|
| `browser_status` | Check gateway/browser availability |
| `browser_navigate` | Go to URL, returns snapshot |
| `browser_snapshot` | Get accessibility tree with refs |
| `browser_screenshot` | Take PNG screenshot (returns image) |
| `browser_click` | Click element by ref |
| `browser_type` | Type into element by ref |
| `browser_press` | Press keyboard key |
| `browser_evaluate` | Run arbitrary JS in page context |
| `browser_wait` | Wait for selector/text/URL/load/JS condition |
| `browser_tabs` | List open tabs |

## Important Notes

- **Refs go stale** after navigation or page mutation. Re-snapshot if clicks/types fail.
- **`browser_evaluate` is the escape hatch** — use it for anything the other tools don't cover (cookies, localStorage, DOM manipulation, dialog dismissal).
- **Persistent sessions** — navigating to authenticated sites uses existing cookies. No need to re-login.
- **Sequential execution** — all commands are serialized. No race conditions.
- **Only http/https** URLs allowed. file://, chrome://, javascript:// are blocked.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Tools return errors | Run `browser_status` — is gateway running? |
| Gateway not running | Run `openclaw browser start` via Bash |
| Extension disconnected | Tell Scott to check Chrome extension status |
| Stale refs | Re-run `browser_snapshot` to get fresh refs |
| Page not loading | Try `browser_wait` with `--load networkidle` |
