---
title: "feat: Browser MCP Server"
type: feat
status: completed
date: 2026-03-10
origin: docs/brainstorms/2026-03-10-browser-mcp-server-brainstorm.md
deepened: 2026-03-10
---

# feat: Browser MCP Server

## Enhancement Summary

**Deepened on:** 2026-03-10
**Agents used:** Architecture Strategist, Security Sentinel, Performance Oracle, Code Simplicity Reviewer, Agent-Native Reviewer, TypeScript Reviewer, Best Practices Researcher, MCP SDK (Context7)

### Key Improvements
1. **Dramatically simplified** — 26 tools → 10 core tools, 8 files → 2 files, 5 phases → 2 phases (~50% less code)
2. **Security hardened** — URL scheme blocking, `--` argument terminator, absolute binary path, no cookie access in v1
3. **Concrete MCP SDK patterns** — Zod schemas, ESM, `McpServer.registerTool()`, image content blocks, stderr-only logging

### Design Decisions from Deepening
- **No driver abstraction in v1** — inline OpenClaw logic directly. Extract interface only if a second driver materializes.
- **No placeholder files** — no `playwright.js`, no `interface.js`. YAGNI.
- **`browser_evaluate` is the escape hatch** — covers cookies, console, form filling, dialog handling in a pinch. Ship specialized tools only when the escape hatch gets painful.
- **ESM + JS with `@ts-check`** — no build step, but get 80% of TypeScript's benefit.

---

## Overview

Build ClawCode's first custom MCP server — a Node.js stdio server that gives Claude Code full browser automation over Scott's real Chrome. Wraps OpenClaw's `openclaw browser` CLI. Replaces the unreliable Playwright MCP and Claude-in-Chrome setups.

## Problem Statement

ClawCode has tried three browser automation approaches and none work reliably:
- **Playwright MCP** — has failed in practice
- **Claude-in-Chrome** — native messaging bridge drops unpredictably (1 success in 5 attempts across Feb-Mar 2026)
- **WebFetch** — blocked by paywalls, bot detection, auth walls

OpenClaw's browser automation (`openclaw browser` CLI) works reliably via a CDP relay server + Chrome extension. The simplest path: wrap it in an MCP server so Claude Code gets native tool access.

(see brainstorm: `docs/brainstorms/2026-03-10-browser-mcp-server-brainstorm.md`)

## Proposed Solution

A Node.js MCP server using `@modelcontextprotocol/sdk` that:
1. Exposes **10 core tools** covering the essential browser automation loop
2. Wraps `openclaw browser <cmd> --json` via `execFile` (no shell)
3. Serializes concurrent tool calls through a promise-chain queue
4. Returns screenshots as base64 MCP image content blocks
5. Defaults to efficient snapshots with sensible size limits

### Architecture

```
Claude Code Session (stdio)
    │
    ▼
Browser MCP Server (Node.js, ESM)
    │
    ├─ Tool registrations (Zod schemas + handlers)
    ├─ Serial queue (promise chain, ~5 lines)
    ├─ execFile wrapper (JSON parse, error mapping)
    │
    ▼
openclaw browser <cmd> --json (child_process.execFile)
    │
    ▼
OpenClaw Gateway (CDP relay, port 18792) → Chrome
```

### Research Insight: No Driver Abstraction Needed

The simplicity reviewer and architecture strategist both flagged the driver interface as premature abstraction. With one driver and no concrete second driver on the horizon (Playwright and Claude-in-Chrome have both failed), an abstract interface adds complexity without value. If a second driver materializes, extract the interface then — you'll have all the concrete methods from the first driver to guide a better abstraction.

## Technical Considerations

### MCP Server Lifecycle
- **Startup:** Server starts via stdio transport when Claude Code launches it. No eager connectivity check — defers to first tool call (OpenClaw gateway may start after Claude Code).
- **Health:** `browser_status` tool checks gateway connectivity on demand. No background health loop.
- **Concurrency:** All tool calls serialized through a simple promise-chain queue (~5 lines). Browser state is inherently sequential — parallel calls would cause race conditions.
- **Timeouts:** Default 30s (matches OpenClaw default). Configurable per-tool via optional `timeout` parameter.
- **Logging:** Use `console.error()` exclusively — stdout is the MCP stdio transport. Never `console.log()`.
- **Signals:** Handle SIGTERM/SIGINT to kill any in-flight `execFile` child processes and avoid orphans.

### Research Insight: Process-per-Call is Correct

The performance oracle confirmed: ~50-110ms overhead per `execFile` call is acceptable for browser automation where actions already take hundreds of milliseconds. The isolation benefit (a hung CDP command doesn't poison subsequent calls) outweighs the latency cost. If this ever becomes a bottleneck, the upgrade path is a sidecar daemon — but don't build that prematurely.

### Screenshot Pipeline
- OpenClaw's `browser screenshot --json` returns `{"media": "/path/to/screenshot.png"}`.
- MCP server reads the file, returns base64-encoded image as an MCP `image` content block:
  ```javascript
  return {
    content: [{
      type: 'image',
      data: fs.readFileSync(path).toString('base64'),
      mimeType: 'image/png'
    }]
  };
  ```
- Temp files cleaned up after encoding.

### Research Insight: Screenshot Memory

Set `maxBuffer` to at least 10MB for screenshot commands. Full-page screenshots of high-DPI pages can exceed Node's default 1MB `maxBuffer`, causing `ERR_CHILD_PROCESS_STDIO_MAXBUFFER_EXCEEDED`. The base64 encoding inflates PNG by ~33%, so a 2MB screenshot becomes ~2.7MB in the buffer.

### Snapshot Sizing
- Default: `--efficient --limit 500` to prevent context window blowout on complex pages.
- Tools accept optional `limit`, `selector`, and `format` params to override.

### Stale Refs
- Refs are invalidated on any navigation or page mutation.
- `browser_navigate` returns a snapshot by default (saves a round-trip).
- `browser_click` accepts optional `snapshot: true` to return post-click snapshot.
- Tool descriptions explicitly warn Claude about ref lifecycle.

### Naming / Coexistence
- **Remove Playwright MCP** from `.mcp.json` — it's unreliable and the tool names would collide.
- **Remove Claude-in-Chrome** reliance — keep the extension installed but don't depend on it.
- New server registered as `browser` in `.mcp.json`. Tools prefixed `mcp__browser__browser_*`.

### Security Considerations

From the security review:

**Shell injection prevention:**
```javascript
import { execFile as execFileCb } from 'node:child_process';
import { promisify } from 'node:util';
import { which } from './utils.js'; // resolve once at startup

const execFile = promisify(execFileCb);
const OPENCLAW_BIN = which('openclaw'); // absolute path, not PATH-resolved per call

// Always use '--' argument terminator before user-controlled values
await execFile(OPENCLAW_BIN, ['browser', 'navigate', '--', url, '--json']);
```

**URL scheme blocking:**
```javascript
function validateUrl(url) {
  const blocked = /^(file|javascript|data|chrome|chrome-extension|about):/i;
  if (blocked.test(url.trim())) {
    throw new Error(`Blocked URL scheme: ${url}`);
  }
  if (!/^https?:\/\//i.test(url.trim())) {
    throw new Error(`Only http/https URLs allowed: ${url}`);
  }
}
```

**No cookie access in v1.** The security reviewer flagged that even read-only cookie access exposes session tokens for banking, email, and cloud services — defeating `httpOnly` browser security boundaries. `browser_evaluate` can read non-httpOnly cookies if truly needed. A dedicated cookie tool that can read httpOnly cookies is a stronger capability and should be considered carefully.

**`browser_evaluate` trust model.** This tool can run arbitrary JS in authenticated page contexts. Acceptable for a single-user system where the AI agent acts on Scott's behalf. The same trust model as having DevTools open.

## MCP Tools (v1 — Core 10)

| Tool | OpenClaw Command | Notes |
|------|-----------------|-------|
| `browser_status` | `status` | Check gateway + browser availability |
| `browser_navigate` | `navigate <url>` | Returns snapshot by default. Validates URL scheme. |
| `browser_snapshot` | `snapshot --efficient` | Accessibility tree with refs |
| `browser_screenshot` | `screenshot` | Returns base64 image content |
| `browser_click` | `click <ref>` | Supports double, right-click, modifiers. Optional `snapshot: true`. |
| `browser_type` | `type <ref> <text>` | Supports --submit, --slowly |
| `browser_press` | `press <key>` | Keyboard key press |
| `browser_evaluate` | `evaluate --fn <code>` | JS escape hatch — covers cookies, console, forms, dialogs |
| `browser_wait` | `wait` | Wait for selector/text/URL/load/JS/time |
| `browser_tabs` | `tabs` | List open tabs (read-only) |

### Why 10, Not 26

The simplicity reviewer's core insight: `browser_evaluate` is a universal escape hatch. It can read cookies (`document.cookie`), read console output, fill forms, dismiss dialogs, and interact with localStorage — all things the specialized tools would do. Ship the specialized tools only when the evaluate workaround becomes painful.

### Add-on-demand (not v2, just "when needed")

| Tool | Trigger to add |
|------|---------------|
| `browser_fill` | When calling `browser_type` 5+ times on the same form |
| `browser_tab_open/close/focus` | When multi-tab workflows become common |
| `browser_dialog` | When an unexpected alert blocks a session |
| `browser_download` / `browser_upload` | When file operations come up |
| `browser_select` | When dropdown-heavy forms appear |
| `browser_scroll` | When click fails because element is off-screen |
| `browser_pdf` | When page-to-PDF is needed |
| `browser_cookies` | After security review of httpOnly implications |
| `browser_console` | When JS debugging through evaluate is too painful |
| `browser_start` / `browser_stop` | If manual lifecycle management is needed |

## File Structure

```
~/source/clawcode/mcp-servers/browser/
├── package.json          # ESM, @modelcontextprotocol/sdk + zod deps
└── index.js              # Everything: server, tools, handlers, queue, CLI wrapper
```

**That's it.** If `index.js` grows past 500 lines, split into `index.js` (server + queue) and `tools.js` (tool definitions + handlers colocated). But start with one file.

**Deployed to:** `~/clawcode/mcp-servers/browser/` (copy specific files, not rsync --delete)

### Research Insight: MCP SDK Patterns

From Context7 and the TypeScript reviewer:

```javascript
// @ts-check
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const server = new McpServer({ name: 'browser', version: '0.1.0' });

// Register tool with Zod schema — gets runtime validation for free
server.registerTool(
  'browser_navigate',
  {
    description: 'Navigate to a URL and return page snapshot. Refs in snapshot are used by browser_click/browser_type.',
    inputSchema: z.object({
      url: z.string().describe('URL to navigate to (http/https only)'),
      timeout: z.number().optional().describe('Timeout in ms (default 30000)')
    })
  },
  async ({ url, timeout }) => {
    validateUrl(url);
    const result = await enqueue(() =>
      runOpenClaw(['navigate', '--', url, '--json'], { timeout })
    );
    // Return snapshot inline to save a round-trip
    const snapshot = await enqueue(() =>
      runOpenClaw(['snapshot', '--efficient', '--limit', '500', '--json'])
    );
    return {
      content: [{ type: 'text', text: snapshot }]
    };
  }
);

// Serial queue — entire implementation
let pending = Promise.resolve();
function enqueue(fn) {
  const result = pending.then(fn);
  pending = result.then(() => {}, () => {}); // swallow errors in chain
  return result;
}

// Start
const transport = new StdioServerTransport();
await server.connect(transport);
console.error('Browser MCP server running on stdio');
```

### Error Handling Pattern

```javascript
// Map CLI failures to MCP error responses — never crash the server
async function runOpenClaw(args, opts = {}) {
  const timeout = opts.timeout || 30000;
  try {
    const { stdout, stderr } = await execFile(
      OPENCLAW_BIN,
      ['browser', ...args],
      { maxBuffer: 10 * 1024 * 1024, timeout }
    );
    const trimmed = stdout.trim();
    if (!trimmed) return { ok: false, error: 'Empty output from CLI' };
    try {
      return JSON.parse(trimmed);
    } catch {
      return { ok: false, error: `Invalid JSON: ${trimmed.slice(0, 200)}` };
    }
  } catch (err) {
    // execFile failure — binary not found, timeout, non-zero exit
    return { ok: false, error: err.message, stderr: err.stderr?.slice(0, 500) };
  }
}

// In tool handler — return isError, don't throw
if (result.ok === false) {
  return { content: [{ type: 'text', text: result.error }], isError: true };
}
```

## Configuration

### .mcp.json entry

```json
{
  "browser": {
    "command": "node",
    "args": ["/Users/jsperson/clawcode/mcp-servers/browser/index.js"],
    "env": {
      "BROWSER_TIMEOUT": "30000"
    }
  }
}
```

### config/mcp-servers.yaml entry

```yaml
browser:
  command: node
  args:
    - mcp-servers/browser/index.js
  transport: stdio
  required_by:
    - browser automation
  setup_notes: >
    Requires OpenClaw gateway running (openclaw browser start).
    Chrome extension "OpenClaw Browser Relay" must be installed and attached.
  env:
    BROWSER_TIMEOUT: "30000"
```

### Remove from .mcp.json

```json
// DELETE this entry:
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--browser", "chrome", "--extension"]
}
```

## Implementation Phases

### Phase 1: Working Server (build everything)

1. Create `~/source/clawcode/mcp-servers/browser/` directory
2. `package.json` with `@modelcontextprotocol/sdk` and `zod` deps, `"type": "module"`
3. `index.js` — full MCP server with all 10 core tools:
   - `runOpenClaw()` helper: execFile + JSON parse + error mapping
   - `enqueue()`: 5-line promise-chain serial queue
   - `validateUrl()`: block dangerous schemes
   - Resolve `OPENCLAW_BIN` absolute path at startup
   - Register all 10 tools with Zod input schemas
   - Screenshot handler: read file → base64 → `{ type: 'image' }` content
   - Snapshot handler: `--efficient --limit 500` defaults
   - Navigate handler: navigate + auto-snapshot in one response
4. `npm install` deps

**Success:** All 10 tools work end-to-end. Navigate to a page, see its snapshot, take a screenshot, click a link, type into a field, run JS.

### Phase 2: Integration + Test

1. Add `browser` entry to `.mcp.json`
2. Remove `playwright` entry from `.mcp.json`
3. Create `skills/browser/SKILL.md` with trigger keywords
4. Update `config/mcp-servers.yaml`
5. Update `data/scouting/capabilities.md`
6. Test with real use cases:
   - Paywalled article (Economist with gift link)
   - Canvas page (authenticated)
   - Form login workflow
7. Update Obsidian project doc with completion status
8. Deploy to `~/clawcode/mcp-servers/browser/`

**Success:** Browser automation works reliably in real ClawCode sessions.

## Acceptance Criteria

### Functional

- [ ] `browser_status` returns structured gateway/browser state
- [ ] `browser_navigate` loads a URL and returns accessibility snapshot
- [ ] `browser_screenshot` returns viewable image in Claude Code conversation
- [ ] `browser_click` + `browser_type` can fill and submit a login form
- [ ] `browser_evaluate` can run arbitrary JS and return results
- [ ] `browser_tabs` lists open tabs
- [ ] Persistent Chrome sessions — navigating to an authenticated site loads with existing cookies
- [ ] Concurrent tool calls are serialized (no race conditions)
- [ ] Dangerous URL schemes (file://, chrome://) are blocked
- [ ] CLI errors return MCP `isError: true` responses, not server crashes

### Non-Functional

- [ ] MCP server starts in <2s
- [ ] Tool calls complete within 30s default timeout
- [ ] Snapshot output stays under 500 lines by default (efficient mode)
- [ ] Screenshot pipeline handles base64 encoding without memory issues (maxBuffer: 10MB)
- [ ] Clean error messages when OpenClaw gateway is down
- [ ] Zero `console.log` calls (stdout is MCP transport)

## Dependencies & Risks

| Risk | Mitigation |
|------|-----------|
| OpenClaw gateway not running | `browser_status` detects; `openclaw browser start` via Bash as workaround |
| OpenClaw CLI output format changes | Pin to known version, defensive JSON parsing with truncated error messages |
| Large snapshots blow context | Default `--efficient --limit 500`, configurable via tool param |
| Chrome extension detaches | Document in skill; `browser_status` surfaces this |
| OpenClaw project abandoned/changed | When needed, extract driver interface and build Playwright/CDP driver |
| Argument injection via URL | `--` terminator before user-controlled values, absolute binary path |
| Screenshot maxBuffer exceeded | Set `maxBuffer: 10 * 1024 * 1024` for screenshot commands |
| Orphaned child processes on shutdown | Handle SIGTERM/SIGINT, kill in-flight execFile children |

## Sources & References

### Origin

- **Brainstorm:** [docs/brainstorms/2026-03-10-browser-mcp-server-brainstorm.md](docs/brainstorms/2026-03-10-browser-mcp-server-brainstorm.md) — Key decisions: MCP server over Bash skill, modular driver interface, OpenClaw as first backend, persistent sessions required.

### Internal References

- `.mcp.json` — existing MCP server config patterns
- `config/mcp-servers.yaml` — declarative MCP server metadata
- `scripts/gmail-mcp-start.sh` — wrapper script pattern for MCP servers
- `~/openclaw/config/browser/chrome-extension/` — OpenClaw's Chrome extension (reference)
- `memory/topics/development.md` — deploy workflow (source → live)

### External References

- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) — `McpServer`, `StdioServerTransport`, tool registration with Zod
- MCP image content: `{ type: 'image', data: base64, mimeType: 'image/png' }`
- MCP error responses: `{ content: [...], isError: true }`

### OpenClaw CLI Reference

- `openclaw browser --help` — 42 subcommands, all supporting `--json`
- Gateway relay: `ws://127.0.0.1:18792` (default CDP port)
- Chrome extension: Manifest V3, uses `debugger` API for CDP bridging

### Review Agent Findings

- **Simplicity:** Cut 26→10 tools, 8→2 files, 5→2 phases. `browser_evaluate` is universal escape hatch.
- **Architecture:** No driver abstraction needed with one driver. Colocate tool defs with handlers.
- **Security:** execFile + `--` terminator + absolute path. Block dangerous URL schemes. No cookie tool in v1.
- **Performance:** 50-110ms per-call overhead acceptable. Set maxBuffer 10MB for screenshots. Serial queue correct.
- **TypeScript reviewer:** ESM, Zod schemas, promise-chain queue, defensive JSON parsing, never console.log.
