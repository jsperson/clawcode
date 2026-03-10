// @ts-check
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { execFile as execFileCb } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile, unlink } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';

const execFile = promisify(execFileCb);

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT = parseInt(process.env.BROWSER_TIMEOUT || '30000', 10);
const BROWSER_PROFILE = process.env.BROWSER_PROFILE || 'openclaw';
const MAX_BUFFER = 10 * 1024 * 1024; // 10 MB — screenshots can be large

// Resolve openclaw binary once at startup (absolute path, no per-call PATH lookup)
let OPENCLAW_BIN;
try {
  OPENCLAW_BIN = execFileSync('which', ['openclaw'], { encoding: 'utf8' }).trim();
} catch {
  console.error('FATAL: openclaw binary not found in PATH');
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Serial queue — browser state is sequential, parallel calls cause races
// ---------------------------------------------------------------------------

let pending = Promise.resolve();

/**
 * @template T
 * @param {() => Promise<T>} fn
 * @returns {Promise<T>}
 */
function enqueue(fn) {
  const result = pending.then(fn);
  pending = result.then(() => {}, () => {}); // swallow errors in chain
  return result;
}

// ---------------------------------------------------------------------------
// OpenClaw CLI wrapper
// ---------------------------------------------------------------------------

/** @type {import('node:child_process').ChildProcess | null} */
let activeChild = null;

/**
 * Run an openclaw browser subcommand and parse JSON output.
 * @param {string[]} args - Arguments after "openclaw browser"
 * @param {{ timeout?: number }} [opts]
 * @returns {Promise<any>}
 */
async function runOpenClaw(args, opts = {}) {
  const timeout = opts.timeout || DEFAULT_TIMEOUT;
  try {
    const child = execFile(
      OPENCLAW_BIN,
      ['browser', '--browser-profile', BROWSER_PROFILE, args[0], '--json', ...args.slice(1)],
      { maxBuffer: MAX_BUFFER, timeout }
    );
    activeChild = child.child ?? null;
    const { stdout, stderr } = await child;
    activeChild = null;

    if (stderr && stderr.trim()) {
      console.error(`[openclaw stderr] ${stderr.trim().slice(0, 300)}`);
    }

    const trimmed = (stdout || '').trim();
    if (!trimmed) return { ok: false, error: 'Empty output from CLI' };

    try {
      return JSON.parse(trimmed);
    } catch {
      // Some commands return plain text — wrap it
      return { ok: true, text: trimmed };
    }
  } catch (err) {
    activeChild = null;
    return {
      ok: false,
      error: /** @type {Error} */ (err).message,
      stderr: /** @type {any} */ (err).stderr?.slice(0, 500)
    };
  }
}

// ---------------------------------------------------------------------------
// URL validation
// ---------------------------------------------------------------------------

const BLOCKED_SCHEMES = /^(file|javascript|data|chrome|chrome-extension|about):/i;

/** @param {string} url */
function validateUrl(url) {
  const trimmed = url.trim();
  if (BLOCKED_SCHEMES.test(trimmed)) {
    throw new Error(`Blocked URL scheme: ${trimmed}`);
  }
  if (!/^https?:\/\//i.test(trimmed)) {
    throw new Error(`Only http/https URLs allowed: ${trimmed}`);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a result as MCP text content */
function textResult(data, isError = false) {
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  return { content: [{ type: /** @type {const} */ ('text'), text }], isError };
}

/** Check if an OpenClaw result indicates failure */
function isFailed(result) {
  return result && result.ok === false;
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new McpServer({
  name: 'browser',
  version: '0.1.0'
});

// --- browser_status ---
server.registerTool(
  'browser_status',
  {
    description: 'Check if OpenClaw gateway and browser are available. Call this first if browser tools fail.',
    inputSchema: z.object({})
  },
  async () => {
    const result = await enqueue(() => runOpenClaw(['status']));
    if (isFailed(result)) return textResult(result, true);
    return textResult(result);
  }
);

// --- browser_navigate ---
server.registerTool(
  'browser_navigate',
  {
    description: 'Navigate to a URL and return an accessibility snapshot. Refs in the snapshot are used by browser_click and browser_type. Only http/https URLs allowed.',
    inputSchema: z.object({
      url: z.string().describe('URL to navigate to (http/https only)'),
      timeout: z.number().optional().describe('Timeout in ms (default 30000)')
    })
  },
  async ({ url, timeout }) => {
    try {
      validateUrl(url);
    } catch (err) {
      return textResult(/** @type {Error} */ (err).message, true);
    }

    const navResult = await enqueue(() =>
      runOpenClaw(['navigate', '--', url], { timeout })
    );
    if (isFailed(navResult)) return textResult(navResult, true);

    // Return snapshot inline — saves a round-trip
    const snapshot = await enqueue(() =>
      runOpenClaw(['snapshot', '--efficient', '--limit', '500'])
    );
    if (isFailed(snapshot)) {
      // Navigation succeeded but snapshot failed — return nav result
      return textResult({ navigated: url, snapshot_error: snapshot.error });
    }
    return textResult(snapshot);
  }
);

// --- browser_snapshot ---
server.registerTool(
  'browser_snapshot',
  {
    description: 'Get an accessibility snapshot of the current page. Returns refs that can be used with browser_click and browser_type. Refs are invalidated after navigation or page mutation — re-snapshot if actions fail.',
    inputSchema: z.object({
      selector: z.string().optional().describe('CSS selector to scope the snapshot'),
      limit: z.number().optional().describe('Max nodes (default 500)'),
      format: z.enum(['ai', 'aria']).optional().describe('Snapshot format (default "ai")')
    })
  },
  async ({ selector, limit, format }) => {
    const args = ['snapshot', '--efficient'];
    if (limit) args.push('--limit', String(limit));
    if (format) args.push('--format', format);
    if (selector) args.push('--selector', selector);

    const result = await enqueue(() => runOpenClaw(args));
    if (isFailed(result)) return textResult(result, true);
    return textResult(result);
  }
);

// --- browser_screenshot ---
server.registerTool(
  'browser_screenshot',
  {
    description: 'Take a screenshot of the current page. Returns an image. Use for visual verification or when snapshot text is insufficient.',
    inputSchema: z.object({
      fullPage: z.boolean().optional().describe('Capture full scrollable page (default false)'),
      selector: z.string().optional().describe('CSS selector for element screenshot'),
      ref: z.string().optional().describe('ARIA ref from snapshot for element screenshot')
    })
  },
  async ({ fullPage, selector, ref }) => {
    const args = ['screenshot'];
    if (fullPage) args.push('--full-page');
    if (selector) args.push('--element', selector);
    if (ref) args.push('--ref', ref);

    const result = await enqueue(() => runOpenClaw(args));
    if (isFailed(result)) return textResult(result, true);

    // OpenClaw returns { media: "/path/to/screenshot.png" } or similar
    const imagePath = result.media || result.path || result.file;
    if (!imagePath) {
      return textResult({ error: 'No image path in screenshot response', result }, true);
    }

    try {
      const imageData = await readFile(imagePath);
      const base64 = imageData.toString('base64');

      // Clean up temp file
      try { await unlink(imagePath); } catch { /* ignore */ }

      return {
        content: [{
          type: /** @type {const} */ ('image'),
          data: base64,
          mimeType: /** @type {const} */ ('image/png')
        }]
      };
    } catch (err) {
      return textResult({ error: `Failed to read screenshot: ${/** @type {Error} */ (err).message}` }, true);
    }
  }
);

// --- browser_click ---
server.registerTool(
  'browser_click',
  {
    description: 'Click an element by ref from a snapshot. Get refs by calling browser_snapshot or browser_navigate first. If the ref is stale, re-snapshot and retry.',
    inputSchema: z.object({
      ref: z.string().describe('Ref ID from snapshot'),
      button: z.enum(['left', 'right', 'middle']).optional().describe('Mouse button (default "left")'),
      double: z.boolean().optional().describe('Double click'),
      modifiers: z.string().optional().describe('Comma-separated modifiers: Shift,Alt,Meta'),
      snapshot: z.boolean().optional().describe('Return a snapshot after clicking (default false)')
    })
  },
  async ({ ref, button, double: dbl, modifiers, snapshot: wantSnapshot }) => {
    const args = ['click', '--', ref];
    if (button) args.push('--button', button);
    if (dbl) args.push('--double');
    if (modifiers) args.push('--modifiers', modifiers);

    const result = await enqueue(() => runOpenClaw(args));
    if (isFailed(result)) return textResult(result, true);

    if (wantSnapshot) {
      const snap = await enqueue(() =>
        runOpenClaw(['snapshot', '--efficient', '--limit', '500'])
      );
      return textResult(snap);
    }

    return textResult(result);
  }
);

// --- browser_type ---
server.registerTool(
  'browser_type',
  {
    description: 'Type text into an element by ref from a snapshot. Get refs by calling browser_snapshot or browser_navigate first.',
    inputSchema: z.object({
      ref: z.string().describe('Ref ID from snapshot'),
      text: z.string().describe('Text to type'),
      submit: z.boolean().optional().describe('Press Enter after typing'),
      slowly: z.boolean().optional().describe('Type slowly (human-like)'),
      snapshot: z.boolean().optional().describe('Return a snapshot after typing (default false)')
    })
  },
  async ({ ref, text, submit, slowly, snapshot: wantSnapshot }) => {
    const args = ['type', '--', ref, text];
    if (submit) args.push('--submit');
    if (slowly) args.push('--slowly');

    const result = await enqueue(() => runOpenClaw(args));
    if (isFailed(result)) return textResult(result, true);

    if (wantSnapshot) {
      const snap = await enqueue(() =>
        runOpenClaw(['snapshot', '--efficient', '--limit', '500'])
      );
      return textResult(snap);
    }

    return textResult(result);
  }
);

// --- browser_press ---
server.registerTool(
  'browser_press',
  {
    description: 'Press a keyboard key (e.g., Enter, Tab, Escape, ArrowDown). Use for keyboard navigation and form submission.',
    inputSchema: z.object({
      key: z.string().describe('Key to press (e.g., Enter, Tab, Escape, ArrowDown, Backspace)')
    })
  },
  async ({ key }) => {
    const result = await enqueue(() => runOpenClaw(['press', '--', key]));
    if (isFailed(result)) return textResult(result, true);
    return textResult(result);
  }
);

// --- browser_evaluate ---
server.registerTool(
  'browser_evaluate',
  {
    description: 'Execute JavaScript in the page context. This is the escape hatch — use it for reading cookies (document.cookie), manipulating DOM, reading localStorage, dismissing dialogs, or anything the other tools cannot do. The function receives an optional element (if ref is provided).',
    inputSchema: z.object({
      fn: z.string().describe('JavaScript function source, e.g., "() => document.title" or "(el) => el.textContent"'),
      ref: z.string().optional().describe('Ref from snapshot — passed as the function argument')
    })
  },
  async ({ fn, ref }) => {
    const args = ['evaluate', '--fn', fn];
    if (ref) args.push('--ref', ref);

    const result = await enqueue(() => runOpenClaw(args));
    if (isFailed(result)) return textResult(result, true);
    return textResult(result);
  }
);

// --- browser_wait ---
server.registerTool(
  'browser_wait',
  {
    description: 'Wait for a condition before proceeding. Use after actions that trigger navigation or async page updates.',
    inputSchema: z.object({
      selector: z.string().optional().describe('CSS selector to wait for (visible)'),
      text: z.string().optional().describe('Wait for text to appear'),
      textGone: z.string().optional().describe('Wait for text to disappear'),
      url: z.string().optional().describe('Wait for URL (supports globs like **/dash)'),
      load: z.enum(['load', 'domcontentloaded', 'networkidle']).optional().describe('Wait for load state'),
      fn: z.string().optional().describe('JS condition to wait for (passed to waitForFunction)'),
      time: z.number().optional().describe('Wait for N milliseconds'),
      timeout: z.number().optional().describe('How long to wait for each condition (default 20000)')
    })
  },
  async ({ selector, text, textGone, url, load, fn, time, timeout }) => {
    const args = ['wait'];
    if (selector) args.push(selector);
    if (text) args.push('--text', text);
    if (textGone) args.push('--text-gone', textGone);
    if (url) args.push('--url', url);
    if (load) args.push('--load', load);
    if (fn) args.push('--fn', fn);
    if (time) args.push('--time', String(time));
    if (timeout) args.push('--timeout-ms', String(timeout));

    const result = await enqueue(() => runOpenClaw(args, { timeout: (timeout || 20000) + 5000 }));
    if (isFailed(result)) return textResult(result, true);
    return textResult(result);
  }
);

// --- browser_tabs ---
server.registerTool(
  'browser_tabs',
  {
    description: 'List open browser tabs. Returns tab IDs, URLs, and titles.',
    inputSchema: z.object({})
  },
  async () => {
    const result = await enqueue(() => runOpenClaw(['tabs']));
    if (isFailed(result)) return textResult(result, true);
    return textResult(result);
  }
);

// ---------------------------------------------------------------------------
// Lifecycle: clean up child processes on shutdown
// ---------------------------------------------------------------------------

function shutdown() {
  if (activeChild && !activeChild.killed) {
    try { activeChild.kill('SIGTERM'); } catch { /* ignore */ }
  }
  process.exit(0);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`Browser MCP server running (openclaw: ${OPENCLAW_BIN})`);
