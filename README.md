# ClawCode

A personal AI agent system that wraps [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's CLI) with persistent identity, memory, scheduled automation, and multiple interfaces. Claude Code does the thinking; ClawCode gives it a life outside the terminal.

## What It Does

ClawCode turns Claude Code from a one-shot CLI tool into a persistent agent with:

- **Discord bot** — conversational interface with session continuity
- **Scheduled tasks** — daily digests, automated workflows via macOS launchd
- **Skills** — modular capabilities (calendar, email, reminders, notes) that Claude loads on demand
- **Memory** — curated knowledge and daily logs that persist across conversations
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

This context is cached at `data/context.cache` and injected into every Claude invocation via `--append-system-prompt`. A file watcher rebuilds the cache when any source file changes.

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
  morning-digest:
    enabled: true
    cron: "0 6 * * *"
    prompt: "Generate my morning digest."
```

`clawcode schedule sync` converts each schedule into a macOS launchd plist. At the scheduled time, launchd runs `scripts/schedule-runner.py <task-name>`, which:

1. Invokes Claude Code with the prompt
2. Posts the response to Discord via REST API
3. Logs the result and updates `data/state.json`

Schedules run independently of the bot — they're native macOS services. They survive bot crashes and restarts.

### Memory

Two-tier system:

- **`MEMORY.md`** — curated long-term knowledge, updated when explicitly asked
- **`memory/YYYY-MM-DD.md`** — daily session logs, appended automatically

Both are indexed with SQLite FTS5 for fast search (`clawcode memory search "<query>"`). Claude is instructed to search memory before reading files directly.

### Gateway (Optional)

An optional WebSocket server (`gateway/`) that sits between clients and Claude Code processes. Instead of spawning a new `claude` subprocess per message, the gateway maintains long-running Claude processes using stream-json I/O.

Benefits: shared processes across clients, persistent sessions, TUI can attach to Discord conversations. Currently disabled — the direct subprocess model is simpler for single-user use.

## Interfaces

### Discord Bot

Primary interface. Runs as a launchd service (`com.clawcode.bot`), auto-starts on login, auto-restarts on crash. Packaged as a `.app` bundle so macOS TCC permissions (Calendar, Reminders) stay stable across restarts.

### CLI

```bash
clawcode                        # Interactive Claude Code session with context
clawcode "what's on my calendar" # One-shot query
clawcode --continue             # Resume last session
clawcode doctor                 # System health check
clawcode schedule list          # View scheduled tasks
clawcode memory search "query"  # Search memory
```

The CLI wrapper changes to `~/clawcode` (so Claude Code loads `.claude/CLAUDE.md` automatically), injects the context cache, and passes through to `claude`.

### TUI

`clawcode tui` connects to the gateway, lists active sessions (including Discord conversations), and lets you attach to one. It hands off to native `claude --resume` for a full interactive terminal experience, then detaches cleanly.

## Directory Structure

```
~/source/clawcode/          # Development (git-connected)
~/clawcode/                 # Production (running instance)
  bot/                      # Discord bot + Claude bridge
  cli/                      # CLI wrapper + TUI client
  config/                   # YAML configuration
  data/                     # Runtime state, logs, databases
  gateway/                  # Optional WebSocket gateway
  launchd/                  # macOS service plists
  memory/                   # Daily session logs
  scripts/                  # Setup, scheduling, utilities
  skills/                   # Skill definitions
  SOUL.md                   # Agent philosophy
  STYLE.md                  # Voice and formatting
  IDENTITY.md               # Persona identity
  USER.md                   # User profile (not committed)
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

## Requirements

- macOS (launchd, EventKit, TCC)
- Python 3.13+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`npm install -g @anthropic-ai/claude-code`)
- Discord bot token
