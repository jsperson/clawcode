# Browser MCP Server for ClawCode

**Date:** 2026-03-10
**Status:** Brainstorm complete, ready for planning

## What We're Building

An MCP server that gives ClawCode full browser automation over Scott's real Chrome — persistent sessions, logged-in cookies, the works. The server exposes a clean set of MCP tools (navigate, snapshot, click, type, screenshot, etc.) and delegates to a swappable backend driver.

The first driver wraps OpenClaw's `openclaw browser` CLI, which is already running and reliable. The architecture allows swapping in Playwright, raw CDP, or anything else later without changing the MCP tool interface.

## Why This Approach

### Problem
- **WebFetch gets blocked** by paywalls, bot detection, auth walls
- **Claude-in-Chrome extension** has been unreliable — native messaging bridge drops unpredictably (failed 2026-02-22, worked 2026-02-25, failed again 2026-02-26)
- **Playwright MCP** has also failed in practice
- **OpenClaw's browser automation works** — CDP relay server + custom Chrome extension + CLI wrapper. Proven reliable.

### Decision: MCP server wrapping `openclaw browser`
- OpenClaw's infrastructure is already running on the Mac Studio
- No need to rebuild CDP relay, Chrome extension, or session management
- MCP server gives Claude Code native tool access (cleaner than Bash shelling)
- Modular backend means we're not permanently coupled to OpenClaw

### Rejected Alternatives
- **Bash-only skill** — Would work, simpler, but less clean integration. Claude Code works better with native MCP tools than parsing Bash output.
- **Rebuild OpenClaw's relay from scratch** — Unnecessary duplication. OpenClaw already solved this.
- **Fix Claude-in-Chrome** — The connection reliability issue is in Anthropic's extension, not something we can fix.
- **Fix Playwright MCP** — Has failed in practice. OpenClaw's approach works.

## Key Decisions

1. **MCP server, not a skill** — Native tool integration beats Bash wrappers
2. **Backend-agnostic design** — Clean driver interface so we can swap OpenClaw for Playwright/CDP/whatever later
3. **OpenClaw as first driver** — It works today, no new infrastructure needed
4. **Persistent sessions required** — Must use Scott's real Chrome with logged-in state (cookies, extensions, etc.)
5. **Full browser control** — Not just page text extraction. Navigate, click, type, screenshot, snapshot, fill forms, read console, handle tabs — the full set

## Architecture

```
Claude Code Session
    |
    v
Browser MCP Server (Node.js)
    |
    v
Driver Interface
    |
    +-- OpenClaw Driver (first) --> `openclaw browser` CLI
    +-- Playwright Driver (future) --> Playwright CDP
    +-- Raw CDP Driver (future) --> Direct WebSocket to Chrome
```

### MCP Tools (proposed)

| Tool | Description |
|------|-------------|
| `browser_navigate` | Navigate to URL |
| `browser_snapshot` | Get page accessibility snapshot (ref-based) |
| `browser_screenshot` | Take screenshot (full page or element) |
| `browser_click` | Click element by ref |
| `browser_type` | Type into element by ref |
| `browser_press` | Press key (Enter, Tab, etc.) |
| `browser_select` | Select dropdown option |
| `browser_fill` | Fill multiple form fields |
| `browser_hover` | Hover over element |
| `browser_drag` | Drag from ref to ref |
| `browser_tabs` | List open tabs |
| `browser_tab_open` | Open new tab |
| `browser_tab_close` | Close tab |
| `browser_tab_focus` | Focus/switch to tab |
| `browser_wait` | Wait for condition (selector, text, load) |
| `browser_evaluate` | Run JS on page |
| `browser_console` | Read console messages |
| `browser_pdf` | Save page as PDF |
| `browser_status` | Check browser/driver status |
| `browser_cookies` | Read/write cookies |

### Driver Interface

Each driver implements:
- `status()` — Is the browser available?
- `navigate(url)` — Go to URL
- `snapshot(opts)` — Get page structure
- `screenshot(opts)` — Capture image
- `click(ref, opts)` — Click element
- `type(ref, text, opts)` — Type text
- `press(key)` — Press key
- `evaluate(fn, ref?)` — Run JS
- `tabs()` — List tabs
- `createTab(url)` — New tab
- `closeTab(id)` — Close tab
- `focusTab(id)` — Switch to tab
- `wait(condition)` — Wait
- `console(opts)` — Console messages
- `cookies(opts)` — Cookie management

### OpenClaw Driver (first implementation)

Thin wrapper — each method shells out to `openclaw browser <command>` with `--json` flag for machine-readable output. Parses JSON response and returns to MCP layer.

Example: `browser_snapshot` calls `openclaw browser snapshot --format aria --json`

## Open Questions

None — all resolved through conversation.

## Resolved Questions

- **Trigger mechanism for fallback from WebFetch?** — Deferred. Build the capability first, worry about automatic diversion later.
- **Interactive or just text extraction?** — Full browser control. Not just a scraper.
- **Own Chrome or clean browser?** — Real Chrome, persistent sessions, logged-in state.
- **Permanent OpenClaw dependency?** — No. Modular driver interface so backend is swappable.
- **Skill vs MCP server?** — MCP server. Cleaner integration with Claude Code.
