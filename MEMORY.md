# MEMORY.md - Agent Memory

## Frameworks & Mental Models

### AI Capex Judgment Framework
**Date:** 2026-02-02

**"Show me the productivity" vs "Trust the capex"** — useful framing for how markets will judge AI infrastructure spending going forward.

**Origin:** W05 2026 macro trends. Meta soared (crediting 30% engineer productivity gains from AI, $65B capex). Microsoft dropped 10% (worst since March 2020). The divergence suggests execution proof is now required — capex alone doesn't cut it.

**Application:** When tracking Big Tech AI investments, watch for concrete productivity metrics vs vague "AI infrastructure" narratives.

---

## System Configuration

### ClawCode Config
**Date:** 2026-02-07

**Project directory:** `~/clawcode/`
- Config: `config/config.yaml`
- Bot code: `bot/`
- Skills: `skills/`
- Identity layer: `SOUL.md` (philosophy), `STYLE.md` (voice), `IDENTITY.md` (presentation), `USER.md` (user profile)
- Memory: `memory/` (daily logs), `MEMORY.md`
- CLI wrapper: `cli/clawcode`

**Backend:** Claude Code CLI (`~/.npm-global/bin/claude`) via Max subscription
- Invoked with `--print --output-format json --session-id <uuid>`
- Sessions tracked per Discord channel, expire after 30 min inactivity

**Runs alongside OpenClaw** — separate systems, no shared state.

---

## User Identity & Accounts

### GitHub & Email
**Date:** 2026-01-24

- **GitHub username:** jsperson
- **Primary email:** jsperson@gmail.com (use for almost everything)

---

## Standard Operating Procedures

### Time & Date Format
**Date:** 2026-01-23

**Time Zone:** US Central Time (America/Chicago) with daylight saving time changes
**Time Format:** 24-hour format (e.g., 14:30, 19:22)
**Date Format:** YYYY-MM-DD (ISO 8601) when technical; human-readable when appropriate

**Examples:**
- `2026-01-23 19:22` (technical context)
- `Jan 23, 2026 at 7:22 PM` (human-readable when needed)
- Always account for DST transitions (CDT/CST)

---

## Interaction Preferences

### Decision-Making Protocol
**Date:** 2026-01-23

When Scott provides specific technical instructions (e.g., "use launchd"), do NOT shift to alternative approaches without explicit discussion first, even if encountering obstacles.

- If the requested approach hits issues: present the problem and proposed alternatives
- Wait for Scott to choose the direction
- Don't assume "getting it working" justifies deviating from explicit instructions

---

## Documentation Maintenance

### When making system changes
1. Commit and push changes to the clawcode repo
2. Update relevant documentation
3. Document new dependencies and troubleshooting steps

### Skill setup docs
When adding a new skill, ensure its `SKILL.md` frontmatter includes `metadata.clawcode.requires.bins` listing all required CLI tools. This powers `clawcode doctor` and `scripts/setup.sh` for automated dependency checking and first-run setup. Update `config/mcp-servers.yaml` if the skill depends on an MCP server.

---

## Workflows & Commands

### Personal Notes Processing
**Date:** 2026-01-23

When Scott asks to "process my new written notes" or similar:

1. **Always check CLAUDE.md first** - Scott documents workflows in his Obsidian vault at `/scott/CLAUDE.md`
2. **Workflow documented there:**
   - Check `Personal Notes/Inbound Notes/` for new PDFs
   - Convert PDF to images (pdftoppm)
   - OCR each page using image tool
   - Insert entries chronologically into `Personal-Notes-YYYY.md`
   - Move processed PDF to `zzArchivedPDFs/`
3. **Don't ask "what should I do?"** - the workflow is documented, just execute it

---

## Scheduling

### Workflow
Schedules are macOS launchd agents, independent of the Discord bot process.

- **Source of truth:** `config/schedules.yaml`
- **Format:** `name`, `cron` (5-field), `prompt`, `enabled`
- **After editing:** run `scripts/schedule-sync.py` to sync to launchd
- **Agents named:** `com.clawcode.schedule.<name>`
- **Runner:** `scripts/schedule-runner.py <name>` — invokes Claude CLI, posts to Discord via REST API
- **Logs:** `data/logs/schedule-<name>.log`
- **CLI:** `clawcode schedule sync|list|logs <name>`

### Key Points
- Schedules fire even if the bot is down
- Sync is idempotent: deletes all agents, recreates from YAML
- Step intervals (e.g., `*/30`) use launchd `StartInterval`; specific times use `StartCalendarInterval`

---

## Planned Features

### Unified CLI / Discord Session
Bridge CLI and Discord into a single shared session so you can move between interfaces within the same conversation — similar to OpenClaw's multi-interface model. Scheduled task output (heartbeat, trends, etc.) would surface in both places.

### Discord Image/Attachment Support
Bot ignores `message.attachments`. Would need to download images and route to Claude via Anthropic API (CLI doesn't support image input via stdin). Enables image analysis, OCR, screenshot interpretation.

---

## Completed Features

### Memory Search — 2026-02-08
- `bot/memory_search.py` — SQLite FTS5 full-text search over MEMORY.md + daily logs
- BM25 ranking with porter stemming, lazy mtime-based re-indexing
- Chunks MEMORY.md by `###` headings, daily logs by `###` time entries
- CLI: `clawcode memory search|index|stats`
- System prompt instructs Claude to run `clawcode memory search` before reading files directly

### Background Startup — 2026-02-08
- Bot runs as launchd agent (`com.clawcode.bot`) with `KeepAlive` + `RunAtLoad`
- Launches via `ClawCode.app` bundle for stable macOS TCC bundle ID
- `install.sh` re-bootstraps agents after copying plists (no more dead bot after install)

### ClewHub Skill Compatibility + Unified Context Layer — 2026-02-07
- `bot/context.py` — unified context builder assembles identity + user + skill summaries, writes `data/context.cache`
- Context cached in memory at startup, refreshed on file changes (SKILL.md, IDENTITY.md, USER.md) and `!reload`
- CLI reads `data/context.cache` for `--append-system-prompt` — no per-invocation parsing
- `skills/loader.py` — accepts both `metadata.clawcode` and `metadata.clawdbot` namespaces; frontmatter-less fallback; platform/binary/env gating; dropped keyword matching
- CLI `clawcode skill list|install|search` subcommands (install/search via `clawdhub` CLI)
- `scripts/doctor.py` — proper YAML parsing for both namespaces, `clawdhub` + context cache checks

### OpenClaw Skill Hooks (ClewHub Compatibility) — 2026-02-07
Skills can now be shared between ClawCode, Clawdbot, and ClewHub via dual-namespace metadata support.

### launchd System Scheduler — 2026-02-07
- Replaced in-process APScheduler with macOS launchd agents
- `scripts/schedule-runner.py` — standalone task runner (Claude CLI + Discord REST)
- `scripts/schedule-sync.py` — YAML-to-launchd plist sync (delete-all/re-push)
- `cli/clawcode schedule sync|list|logs` — CLI subcommands
- `skills/scheduler/SKILL.md` — scheduling workflow skill
- Schedules fire independently of bot process

### Graceful Shutdown / Restart — 2026-02-07
- Signal handling via discord.py `on_close` — fires on SIGTERM or `client.close()`
- Session persistence: `data/sessions.json` (channel → session_id, last_used, message_count)
- `time.time()` wall-clock timestamps survive process restarts (replaced `time.monotonic()`)
- Lifecycle markers: startup/shutdown in daily log + `data/state.json` timestamps
- `!restart` Discord command: sends message, calls `client.close()`, launchd restarts
- `clawcode restart` CLI: `launchctl kickstart -k` for terminal-initiated restarts
- File watcher cleanup on shutdown (`observer.stop()` + `observer.join(timeout=5)`)

### Gmail MCP Server — 2026-02-07
- `gmail-mcp` (npm, domdomegg) running as **stdio** MCP server
- OAuth credentials via Google Cloud project `gogcli-clawdbot` (Web Application: `clawcode-gmail-mcp`)
- One-time setup: `scripts/gmail-oauth-setup.sh` gets refresh token, stores in `.env`
- Wrapper `scripts/gmail-mcp-start.sh` exchanges refresh token for access token on each invocation
- Registered via `claude mcp add gmail-mcp -- ~/clawcode/scripts/gmail-mcp-start.sh`
- Skill: `skills/gmail/SKILL.md`
- Doctor checks: OAuth creds + refresh token in `.env`
- Note: HTTP transport had OAuth bugs in Claude Code — stdio with pre-fetched token is the reliable path

---

## Skills Available

### Calendar Integration - icalpal
**Date:** 2026-01-23

The **icalpal** skill provides macOS Calendar/Reminders access via CLI.

**When to use:**
- Calendar queries (today, tomorrow, next week, etc.)
- Meeting lookups
- Event formatting for digests or notes

**Tool:** Uses `icalpal` CLI tool (installed via Homebrew)

### Apple Reminders - remindctl
**Date:** 2026-02-07

The **apple-reminders** skill manages Apple Reminders via `remindctl` CLI.

**When to use:**
- Create reminders ("remind me to...")
- List tasks (today, overdue, by list)
- Complete or delete reminders

**Tool:** Uses `remindctl` CLI tool (installed via Homebrew)

### Scheduler - launchd
**Date:** 2026-02-07

The **scheduler** skill manages recurring tasks via macOS launchd agents.

**When to use:**
- Add, modify, remove, enable/disable scheduled tasks
- Check schedule status
- Any "every day", "every hour", "recurring", "cron" requests

**Tool:** Edits `config/schedules.yaml` + runs `scripts/schedule-sync.py`

### Gmail - gmail-mcp
**Date:** 2026-02-07

The **gmail** skill provides full Gmail access via MCP (search, read, send, draft, archive, labels, filters, attachments).

**When to use:**
- Check email, search inbox
- Read threads, send/draft emails
- Manage labels and filters

**Tool:** `gmail-mcp` HTTP MCP server on port 9025. Draft-first for new emails — always confirm before sending.
