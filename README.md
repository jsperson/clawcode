# ClawCode

A personal AI agent system that wraps [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's CLI) with persistent identity, memory, scheduled automation, and multiple interfaces. Claude Code does the thinking; ClawCode gives it a life outside the terminal.

## What It Does

ClawCode turns Claude Code from a one-shot CLI tool into a persistent agent with:

- **Discord bot** — conversational interface with session continuity, file attachments, and message queuing
- **Scheduled tasks** — daily digests, automated workflows, and recurring jobs via macOS launchd
- **Skills** — modular capabilities (calendar, email, reminders, notes, Canvas LMS) that Claude loads on demand
- **Memory** — curated knowledge and daily logs with full-text search across conversations
- **CLI wrapper** — enhanced terminal access with context injection
- **TUI** — attach to active Discord sessions from the terminal

The system is designed for a single user. It knows who it's talking to, remembers past conversations, and has opinions.

## How It Works

### Claude Code as the Engine

ClawCode doesn't implement its own LLM interface. Every interaction — Discord messages, scheduled tasks, CLI queries — ultimately invokes the `claude` CLI binary. ClawCode's job is to manage the context, sessions, and routing around it.

```
User ──→ Interface ──→ ClawCode ──→ claude CLI ──→ Response ──→ Interface
         (Discord,      (context,    (subprocess)
          CLI, TUI,      sessions,
          scheduler)     skills)
```

### Invocation

The bot calls Claude Code as a subprocess:

```bash
claude --print --output-format json \
  --dangerously-skip-permissions \
  --add-dir ~/vault \
  --mcp-config data/.mcp-config.json \
  --resume <session-uuid> \
  --append-system-prompt <context>
```

Key flags:
- `--print` runs non-interactively, outputting the response to stdout
- `--resume` continues an existing session, preserving conversation history
- `--append-system-prompt` injects ClawCode's context (identity, skills, memory instructions)
- `--add-dir` gives Claude read/write access to the Obsidian vault
- `--mcp-config` registers MCP tool servers (Gmail, etc.)

User messages are piped via stdin. Responses come back as JSON on stdout.

### Session Management

Each Discord channel gets a persistent session UUID. On the first message, ClawCode creates a new session (`--session-id`). Follow-up messages resume it (`--resume`). Sessions expire after 30 minutes of inactivity. Session state survives bot restarts via `data/sessions.json`.

A semaphore ensures only one Claude invocation runs at a time — Claude Code doesn't support concurrent access to the same session.

### Context Injection

On startup, ClawCode builds a context payload from:

| Source | Content |
|--------|---------|
| `SOUL.md` | Agent philosophy, values, boundaries |
| `STYLE.md` | Voice, tone, formatting rules |
| `IDENTITY.md` | Persona (name, creature type, vibe) |
| `USER.md` | User profile, preferences, family, goals |
| `skills/*/SKILL.md` | Name + description of each eligible skill |

This context is cached at `data/context.cache` and injected into every Claude invocation via `--append-system-prompt`. A watchdog file watcher monitors all source files and rebuilds the cache automatically when any of them change — no restart required.

Skills are loaded lazily: only names and one-line descriptions go into the context. When Claude decides it needs a skill, it reads the full `SKILL.md` itself using its file read tool.

### Skills

Skills live in `skills/<name>/SKILL.md` with YAML frontmatter:

```yaml
---
name: gmail
description: Search, read, send, and manage Gmail
metadata:
  clawcode:
    requires:
      mcp_servers: [gmail-mcp]
---
```

The loader (`skills/loader.py`) scans all skills at startup and checks eligibility: correct platform, required binaries present, environment variables set, MCP servers available. Only eligible skills appear in Claude's context.

Skills don't add code to ClawCode — they add *knowledge* to Claude. A skill body is just instructions and examples that Claude reads when it needs to perform that capability.

### MCP Servers

[Model Context Protocol](https://modelcontextprotocol.io/) servers give Claude access to external tools. ClawCode configures them declaratively in `config/mcp-servers.yaml`:

```yaml
servers:
  gmail-mcp:
    transport: stdio
    command: ~/clawcode/scripts/gmail-mcp-start.sh
    env:
      GOOGLE_CLIENT_ID: "${GOOGLE_CLIENT_ID}"
```

At startup, this is converted to the JSON format Claude Code expects and written to `data/.mcp-config.json`. Environment variables are expanded from `.env`.

### Scheduled Tasks

Schedules are defined in `config/schedules.yaml`:

```yaml
schedules:
  daily_digest:
    enabled: true
    cron: "0 7 * * *"
    script: "bash ~/clawcode/scripts/daily-digest.sh"

  reminder_check:
    enabled: true
    cron: "0 * * * *"
    prompt: "Check remindctl for overdue items. Surface anything needing attention."
```

`clawcode schedule sync` converts each schedule into a macOS launchd plist. At the scheduled time, launchd runs `scripts/schedule-runner.py <task-name>`, which:

1. Tasks with `script:` — runs the shell command directly, captures stdout
2. Tasks with `prompt:` — invokes Claude Code CLI with the prompt
3. Posts the result to Discord via REST API (works independently of the bot process)
4. Updates `data/state.json` with last-run timestamp

Schedules run independently of the bot — they're native macOS services. They survive bot crashes and restarts.

#### Default Schedules

| Schedule | Frequency | Purpose |
|----------|-----------|---------|
| `heartbeat` | Every 4 hours | Reads `HEARTBEAT.md`, executes active maintenance tasks |
| `life_overnight` | 02:00 daily | Runs the `/life:overnight` planning workflow |
| `daily_backup` | 01:00 daily | Archives critical data |
| `daily_digest` | 07:00 daily | Generates morning briefing → Obsidian vault |
| `reminder_check` | Hourly | Surfaces overdue and due-today items |
| `end_of_day` | 18:00 daily | Summarizes the day, writes to daily log |
| `weekly_review` | Sun 16:00 | Synthesizes the week's logs, suggests MEMORY.md promotions |
| `weekly_trends` | Mon 03:00 | Macro trends analysis (tech, markets, geopolitics) |

### Memory

Two-tier system:

- **`MEMORY.md`** — curated long-term knowledge: preferences, decisions, technical gotchas, recurring patterns. Updated when explicitly asked.
- **`memory/YYYY-MM-DD.md`** — daily session logs, appended automatically by the bot in real-time with timestamps.

Both are indexed with SQLite FTS5 (Porter stemming, BM25 relevance scoring) for fast retrieval. The index updates lazily based on file modification times — no manual rebuilds needed.

```bash
clawcode memory search "cycling preferences"           # Search both memory and daily logs
clawcode memory search "Django errors" --source daily  # Daily logs only
clawcode memory search "Newman courses" --limit 10     # Up to 10 results
clawcode memory stats                                  # Index statistics
clawcode memory index                                  # Force full re-index
```

Claude is instructed to always search memory before claiming it doesn't remember something.

### Gateway (Optional)

An optional WebSocket server (`gateway/`) that sits between clients and Claude Code processes. Instead of spawning a new `claude` subprocess per message, the gateway maintains long-running Claude processes using stream-json I/O.

Benefits: shared processes across clients, persistent sessions, streaming responses, TUI can attach to Discord conversations. The gateway client includes auto-reconnect with exponential backoff (2^n seconds, max 60s) and session restoration on reconnection.

Currently disabled — the direct subprocess model is simpler for single-user use.

## Interfaces

### Discord Bot

Primary interface. Runs as a launchd service (`com.clawcode.bot`), auto-starts on login, auto-restarts on crash. Packaged as a `.app` bundle (`ClawCode.app`) so macOS TCC permissions (Calendar, Reminders) stay stable across restarts.

#### Commands

Synchronous commands are processed immediately, bypassing the message queue:

- `!status` — show current task duration and queue depth
- `!cancel` — cancel the running task and clear the message queue
- `!reload` — rebuild context cache from disk (SOUL.md, STYLE.md, skills, etc.)
- `!restart` — graceful shutdown; launchd auto-restarts the service

#### Attachments

Discord file attachments are downloaded and passed to Claude automatically:

- **Images** (PNG, JPEG, GIF, WebP) — validated via magic bytes, base64-encoded as image content blocks
- **Text files** (.py, .txt, .json, .csv, .md, .yaml, .xml, .html, etc.) — base64-encoded as text blocks
- **Binary files** — saved to `/tmp/clawcode-attachments/` with path reference so Claude can use its Read tool

Limits: 10 MB per file, 5 attachments per message. Duplicate filenames get collision suffixes.

#### Message Queue

Each channel has a FIFO message queue (max 5). When Claude is busy processing a message:

- New messages are queued with an hourglass (⏳) reaction
- Messages drain in order as tasks complete
- If the queue is full, new messages are rejected with a notification
- `!cancel` clears the active task and the entire queue (checkmark ✅ on cancelled messages)

#### Error Recovery

When Claude's context grows too large (typically after many exchanges in a session), the bot auto-detects the error, clears the session, and retries with fresh context. A Discord notification explains the reset.

If a session UUID conflicts (e.g., another process is using it), the bot creates a fresh session and retries transparently.

#### Response Handling

- **Direct CLI mode** — heartbeat status updates every 15 seconds showing elapsed time while Claude works
- **Gateway mode** — streaming responses with progressive Discord message edits every 3 seconds
- Long responses are automatically split across multiple Discord messages, respecting paragraph and line boundaries (2000-char Discord limit)

#### Lifecycle

- On startup: logs to daily memory, posts "Online" status to Discord, connects to gateway if enabled
- On shutdown (SIGTERM): posts "Offline" status, persists sessions to disk, disconnects gateway, logs graceful shutdown
- Conversation logging: every exchange is automatically appended to `memory/YYYY-MM-DD.md` with timestamps

### CLI

```bash
clawcode                          # Interactive Claude Code session with context
clawcode "what's on my calendar"  # One-shot query
clawcode --continue               # Resume last session
clawcode doctor                   # System health check
clawcode schedule list            # View scheduled tasks
clawcode schedule sync            # Rebuild launchd plists from schedules.yaml
clawcode memory search "query"    # Search memory and daily logs
clawcode memory stats             # Show search index statistics
clawcode memory index             # Force full re-index
```

The CLI wrapper changes to `~/clawcode` (so Claude Code loads `.claude/CLAUDE.md` automatically), injects the context cache, and passes through to `claude`.

### TUI

`clawcode tui` connects to the gateway, lists active sessions (including Discord conversations), and lets you attach to one. It hands off to native `claude --resume` for a full interactive terminal experience, then detaches cleanly.

## Skills

Skills are modular capability definitions that teach Claude how to use specific tools and services. Each skill is a markdown file with eligibility gates — Claude only sees skills whose requirements are met on the current system.

| Skill | Description | Requires |
|-------|-------------|----------|
| **apple-reminders** | Create, list, complete, and query Apple Reminders | `remindctl` binary (macOS) |
| **calendar-ical** | Read and create macOS Calendar events via native EventKit | `ical` CLI (macOS) |
| **canvas** | Query Newman University Canvas LMS — assignments, grades, submissions, quizzes (112 commands) | Python 3 |
| **daily-digest** | Generate morning briefing with calendar, tasks, projects, and Canvas data | `remindctl`, `ical`, `jq` |
| **gmail** | Search, read, send, draft, archive, and label emails via 40+ MCP tools | `gmail-mcp` server |
| **notes-inbound** | OCR and archive handwritten note PDFs from Obsidian Inbox | `pdftoppm` |
| **scheduler** | Add, modify, enable/disable recurring scheduled tasks via launchd | `launchctl` (macOS) |
| **scott-vault** | Obsidian vault structure, folder routing, and content filing conventions | macOS |

## Features

### Core
- **Persistent identity** — SOUL.md, STYLE.md, IDENTITY.md define who the agent is across every interaction
- **User profile** — USER.md gives Claude context about the user's life, preferences, and goals
- **Session continuity** — Discord conversations persist across messages with automatic session resume
- **Context caching** — identity, skills, and memory instructions assembled once, hot-reloaded on file changes
- **Concurrency control** — semaphores prevent overlapping Claude invocations (separate queues for user messages and scheduled tasks)

### Discord Bot
- **File attachments** — images validated via magic bytes and base64-encoded; text files decoded inline; binaries saved with path references
- **Message queue** — per-channel FIFO queue (max 5) with emoji feedback (⏳ queued, ✅ cancelled)
- **Streaming responses** — progressive Discord message edits every 3 seconds (gateway mode)
- **Heartbeat status** — elapsed time updates every 15 seconds while Claude works (direct CLI mode)
- **Context overflow recovery** — auto-detects prompt-too-long errors, clears session, retries with fresh context
- **Session conflict recovery** — detects in-use sessions, transparently creates a fresh one
- **Bot commands** — `!restart`, `!reload`, `!cancel`, `!status` processed immediately outside the queue
- **Graceful lifecycle** — SIGTERM handling, session persistence, Discord online/offline status messages
- **Auto-logging** — every exchange appended to `memory/YYYY-MM-DD.md` in real-time
- **Hot reload** — watchdog monitors identity and skill files, rebuilds context cache without restart
- **TCC stability** — packaged as `.app` bundle so macOS Calendar/Reminders permissions survive restarts

### Memory & Search
- **Curated knowledge** — MEMORY.md for long-term facts, decisions, and preferences
- **Daily logs** — automatic conversation logging to `memory/YYYY-MM-DD.md` with timestamps
- **Full-text search** — SQLite FTS5 index with Porter stemming and BM25 relevance ranking
- **Search CLI** — `clawcode memory search`, `clawcode memory stats`, `clawcode memory index`
- **Lazy indexing** — automatic incremental updates based on file modification times

### Automation
- **Scheduled tasks** — cron-style definitions in YAML, executed as native macOS launchd agents
- **Dual execution modes** — `script:` runs shell commands directly; `prompt:` invokes Claude Code CLI
- **Default schedules** — heartbeat, life overnight planning, daily digest, daily backup, hourly reminder check, end-of-day summary, weekly review, weekly trends
- **Discord integration** — schedule runner posts results via REST API independently of the bot process
- **State tracking** — last-run timestamps in `data/state.json`
- **File watcher** — monitors skill and identity files, rebuilds context cache on changes

### Integration
- **MCP servers** — declarative config for Model Context Protocol tool servers (Gmail, etc.)
- **Obsidian vault** — read/write access to the user's knowledge base
- **macOS services** — launchd for bot lifecycle, TCC-stable .app bundles for system permissions
- **Discord REST API** — scheduled tasks post directly without the bot process
- **Life Agent** — overnight planning workflow generates daily plans from calendar, tasks, and principles

### Infrastructure
- **Gateway** (optional) — WebSocket server for shared Claude processes and multi-client routing, with auto-reconnect and session restoration
- **Health checks** — `clawcode doctor` validates Python version, Claude CLI, Discord config, skill dependencies, vault access, and launchd services
- **Installer** — single-script setup: virtualenv, Swift binary compilation, .app bundles, launchd services, CLI symlinks
- **Daily digest** — `scripts/daily-digest.sh` collects tasks, calendar, Canvas assignments, and active projects into an Obsidian vault note

## Directory Structure

```
~/source/clawcode/          # Development (git-connected)
~/clawcode/                 # Production (running instance)
  bot/                      # Discord bot + Claude bridge
    main.py                 # Bot entry point, message handling, queue, lifecycle
    claude_bridge.py        # Claude CLI invocation, session management
    gateway_client.py       # WebSocket client for gateway mode
    context.py              # Context cache builder (SOUL + STYLE + skills)
    memory.py               # MEMORY.md and daily log I/O
    memory_search.py        # SQLite FTS5 search engine
    file_watcher.py         # Watchdog vault monitoring
    scheduler.py            # Schedule state tracking
    config.py               # YAML config + env var expansion
  cli/                      # CLI wrapper + TUI client
  config/                   # YAML configuration
    config.yaml             # Discord, Claude, gateway, file watch settings
    schedules.yaml          # Scheduled task definitions
    mcp-servers.yaml        # MCP server declarations
  data/                     # Runtime state, logs, databases
    context.cache           # Pre-built identity + skills context
    sessions.json           # Discord channel → Claude session mapping
    memory.db               # SQLite FTS5 search index
    state.json              # Last-run timestamps, bot lifecycle events
    .mcp-config.json        # Generated MCP config for Claude CLI
  gateway/                  # Optional WebSocket gateway
  launchd/                  # macOS service plists
  memory/                   # Daily session logs (YYYY-MM-DD.md)
  scripts/                  # Setup, scheduling, utilities
    install.sh              # Full installer (virtualenv, binaries, services)
    schedule-runner.py      # Invoked by launchd for scheduled tasks
    schedule-sync.py        # Converts schedules.yaml → launchd plists
    daily-digest.sh         # Morning briefing generator
    doctor.py               # Health check (dependencies, config, permissions)
    backup.sh               # Vault backup
  skills/                   # Skill definitions (SKILL.md per capability)
  bin/                      # Compiled binaries
  ClawCode.app/             # macOS .app bundle for TCC permissions
  ClawCodeGateway.app/      # Gateway .app bundle
  SOUL.md                   # Agent philosophy
  STYLE.md                  # Voice and formatting
  IDENTITY.md               # Persona identity
  USER.md                   # User profile (not committed)
  MEMORY.md                 # Curated long-term knowledge
  HEARTBEAT.md              # Active maintenance tasks for heartbeat schedule
  .env                      # Secrets (not committed)
```

## Setup

```bash
# Clone and install
git clone <repo> ~/source/clawcode
~/source/clawcode/scripts/install.sh

# Configure
edit ~/clawcode/.env          # Discord token, Google OAuth credentials

# Optional: Gmail
~/clawcode/scripts/gmail-oauth-setup.sh

# Optional: Canvas LMS
echo "YOUR_TOKEN" > ~/.config/canvas/token

# Verify
clawcode doctor
```

The `doctor` command checks: Python 3.11+ installed, Claude CLI available, Discord token configured, required binaries for enabled skills present, Obsidian vault path accessible, and launchd services loaded. Pass/Warn/Fail output with fix suggestions.

## Requirements

- macOS (launchd, EventKit, TCC)
- Python 3.13+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`npm install -g @anthropic-ai/claude-code`)
- Discord bot token
