---
topic: Unified Gateway Architecture
date: 2026-02-08
status: draft
---

# Unified Gateway Architecture

## What We're Building

A gateway process that sits between all ClawCode interfaces (Discord, CLI TUI, schedule runner) and the Claude Code CLI. The gateway owns session management, message routing, and conversation history. Discord and CLI become equal clients with separate sessions but shared capabilities (memory, context, skills). Pushed messages (schedule output, lifecycle events) surface in both interfaces.

## Why This Approach

### The Core Constraint

ClawCode uses the Claude Code CLI (`claude`) with a Max subscription — no API key, no per-message cost. Every AI invocation must go through the `claude` binary as a subprocess. This rules out a pure API-based gateway like OpenClaw's, but the gateway pattern still works if the gateway manages claude CLI processes instead of making API calls.

### What Each Interface Needs

**Discord bot:**
- Receives messages from Discord users
- Posts responses back to Discord
- Shows scheduled task output
- Lifecycle messages (online/offline)

**CLI TUI:**
- Interactive terminal chat (like OpenClaw's TUI)
- Full Claude Code experience — tool use, file editing, cancellation
- Receives pushed messages (schedule output, notifications)
- Shared memory and context with Discord
- Can query session history ("what happened while I was offline?")

**Schedule runner:**
- Fires on cron via launchd
- Sends prompt to gateway
- Response posted to Discord (and available to CLI)

### Why Not "Bot as Gateway"

The simpler approach (CLI connects to the running Discord bot) was rejected because:
- CLI would lose Claude Code's native features (interactive tool use, cancellation, streaming)
- Bot failure would degrade CLI
- Tighter coupling between Discord-specific code and session management

### OpenClaw's Influence

OpenClaw uses a WebSocket gateway that all interfaces connect to as clients. Key patterns to adopt:
- Gateway owns sessions and history
- Clients connect via WebSocket, receive streaming events
- TUI is a proper chat client, not a thin wrapper
- Sessions are separate per interface but share the same agent capabilities
- `/deliver` toggle controls whether responses also post to channels

Key difference: OpenClaw's gateway calls the Anthropic API directly. Ours spawns `claude` CLI processes.

## Key Decisions

1. **Gateway is a separate process** — not the Discord bot. Runs via launchd, always on.
2. **Claude CLI is the AI backend** — gateway spawns/manages claude subprocesses using Max subscription auth. No API keys.
3. **Separate sessions per interface** — Discord and CLI have their own conversation threads, not a shared session.
4. **Shared memory** — both interfaces read/write the same MEMORY.md, daily logs, and memory search index.
5. **Shared context** — same identity, user profile, and skills injected regardless of interface.
6. **WebSocket protocol** — clients connect via local WebSocket (like OpenClaw's `ws://127.0.0.1:<port>`).
7. **Push model** — gateway pushes schedule output, lifecycle events, and notifications to all connected clients.
8. **Session history** — gateway persists conversation history so clients can catch up after reconnecting.

## Architecture Sketch

```
  launchd
    │
    ├── Gateway (Python, always running)
    │     ├── WebSocket server (ws://127.0.0.1:PORT)
    │     ├── Session manager (per-client sessions)
    │     ├── Claude CLI process manager (spawn, resume, cancel)
    │     ├── Context builder (identity + user + skills)
    │     ├── Memory (shared read/write, search index)
    │     └── Schedule executor (cron-triggered prompts)
    │
    ├── Discord Bot (Python, connects as WS client)
    │     ├── Discord ↔ Gateway message bridge
    │     ├── Posts responses to Discord channel
    │     └── Lifecycle messages (online/offline dots)
    │
    └── CLI TUI (Python, connects as WS client)
          ├── Terminal chat UI (input, chat log, status)
          ├── Streaming response display
          ├── Push message display
          └── Session history query
```

**Schedule runner** is absorbed into the gateway — no longer a separate script. Gateway has a built-in scheduler that fires prompts on cron.

## Resolved Decisions

1. **Claude CLI session model: Long-running per session.** The gateway keeps a claude CLI process alive per session using bidirectional JSON streaming (`--input-format=stream-json --output-format=stream-json --verbose`). Messages are sent as JSON objects on stdin, responses stream back as JSON events on stdout. This preserves tool use, cancellation, and session context without restarting the process per message. Discord sessions use the same streaming model (not `--print` mode).

2. **TUI implementation: Wrap claude CLI's own interactive mode.** Rather than building a custom TUI from scratch with Textual/curses, the CLI TUI wraps claude's native interactive terminal experience and intercepts I/O. This preserves all Claude Code features (tool use approval, file diffs, syntax highlighting, cancellation) without reimplementing them. The gateway mediates — TUI client sends keystrokes/input to the gateway, which relays to the claude process's pty.

3. **CLI cancellation: SIGINT to the claude process.** When TUI user hits Esc/Ctrl-C, the gateway sends SIGINT to the claude CLI subprocess. Claude handles this gracefully (cancels current tool execution, returns to prompt).

## Open Questions

4. **Gateway language:** Python (consistent with current codebase) or Node.js (better WebSocket ecosystem, closer to OpenClaw's pattern)? Leaning Python for consistency.

5. **Migration path:** How do we incrementally move from current architecture to gateway model without breaking the working Discord bot?

6. **Concurrency:** Multiple sessions (Discord + CLI) may want to invoke claude simultaneously. Current bot has a semaphore limiting to 1. Do we keep that limit or allow parallel invocations (Max subscription may have rate limits)?

## What This Replaces

- `bot/claude_bridge.py` — session management and claude invocation moves to gateway
- `scripts/schedule-runner.py` — absorbed into gateway's scheduler
- `cli/clawcode` (interactive/one-shot modes) — replaced by TUI client + one-shot client
- `cli/clawcode` (subcommands like doctor, skill, schedule) — stay as-is, they don't need the gateway

## What Stays the Same

- Skills system (`skills/*/SKILL.md`, `skills/loader.py`)
- Memory system (MEMORY.md, daily logs, memory_search.py)
- Context builder (`bot/context.py`)
- Config system (`config/config.yaml`, `config/schedules.yaml`)
- Doctor (`scripts/doctor.py`)
- Install process (`scripts/install.sh`)
