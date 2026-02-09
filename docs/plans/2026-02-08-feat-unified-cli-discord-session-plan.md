---
title: Unified CLI / Discord Session
type: feat
date: 2026-02-08
status: superseded
superseded_by: ../brainstorms/2026-02-08-unified-gateway-architecture-brainstorm.md
---

> **Superseded** — This "bot as gateway" approach was rejected in favor of a separate gateway process. See the [unified gateway brainstorm](../brainstorms/2026-02-08-unified-gateway-architecture-brainstorm.md).

# Unified CLI / Discord Session

## Overview

Bridge CLI and Discord into a single shared session. The CLI joins the active Discord conversation (same Claude Code session), and messages from either interface are visible in both places. Scheduled task output also surfaces in Discord.

## Problem Statement

Today ClawCode has three disconnected interfaces:

1. **Discord bot** — rich session management (per-channel UUID, resume, persistence), concurrency control, context injection. This is the primary interface.
2. **CLI** (`clawcode`) — stateless. Every invocation is a fresh Claude Code call with no session continuity. Output only appears in the terminal.
3. **Schedule runner** — stateless. Posts output to Discord via REST but doesn't participate in sessions.

You can't start a conversation in Discord and continue it from the terminal. CLI work is invisible in Discord. There's no shared session state.

## Proposed Solution

### Core Architecture: Message Bus + Shared Session Store

Introduce a lightweight message bus (Unix domain socket or file-based) that both CLI and Discord bot connect to. The bot is the session owner — CLI acts as a second input/output channel into the same session.

```
                    ┌─────────────┐
  Discord User ───> │             │ ───> Discord Channel
                    │  Bot (main) │
  CLI User ───────> │  Session    │ ───> Terminal stdout
                    │  Owner      │
  Schedule ───────> │             │ ───> Discord Channel
                    └──────┬──────┘
                           │
                    Claude Code CLI
                    (single session)
```

### Key Design Decisions

**The bot owns the session.** CLI doesn't invoke Claude Code directly anymore — it sends messages to the bot, which routes them through ClaudeBridge. This preserves:
- Concurrency control (semaphore)
- Session continuity (same UUID)
- Context injection (same append-system-prompt)

**CLI becomes a client, not a standalone invoker.** The `clawcode` CLI sends a message to the running bot and streams the response back. If the bot is down, it falls back to direct Claude Code invocation (current behavior).

**Discord sees everything.** All messages and responses flow through the bot, so Discord always has the full conversation. CLI output appears in Discord as bot messages (with a marker like `[cli]`).

## Technical Approach

### Phase 1: IPC Channel (Bot ↔ CLI)

Add a Unix domain socket server to the bot that accepts messages from the CLI.

**Bot side** (`bot/ipc.py` — new file):
- Asyncio Unix socket server at `data/clawcode.sock`
- Accepts JSON messages: `{"type": "message", "text": "...", "source": "cli"}`
- Routes through existing `ClaudeBridge.invoke()` using the Discord channel's session
- Streams response back to CLI socket
- Posts both the CLI message and response to Discord channel (marked with source)

**CLI side** (`cli/clawcode` — modify):
- For one-shot queries: connect to socket, send message, read response, print, exit
- For interactive mode: connect to socket, REPL loop
- Fallback: if socket doesn't exist (bot down), use current direct invocation

**Socket lifecycle:**
- Created on bot startup, removed on shutdown
- File lock or PID check to prevent stale sockets

### Phase 2: Discord Message Attribution

When a message arrives via CLI, the bot posts it to Discord with attribution:

```
[cli] what events do I have tomorrow?
```

Response appears normally (from the bot). This gives full visibility in Discord.

When a message arrives via Discord, the CLI doesn't need to see it (unless in interactive/watch mode — Phase 3).

### Phase 3: CLI Watch Mode (Optional)

`clawcode --watch` tails the conversation in real-time, showing Discord messages as they arrive. Makes the CLI a full mirror of the Discord channel.

This is optional and can be deferred — the core value is CLI → Discord, not Discord → CLI.

### Phase 4: Schedule Runner Integration

Modify `schedule-runner.py` to use the IPC socket instead of direct Claude invocation + REST posting. Benefits:
- Scheduled tasks share the session (context continuity)
- No duplicate REST posting logic
- Concurrency control via bot's semaphore

Fallback: if bot is down, schedule runner reverts to current direct invocation + REST.

## Acceptance Criteria

### Functional Requirements

- [ ] CLI messages route through bot's session (same Claude Code session as Discord)
- [ ] CLI messages appear in Discord channel with `[cli]` attribution
- [ ] CLI responses print to terminal stdout
- [ ] Bot responses to Discord messages are NOT echoed to CLI (unless watch mode)
- [ ] If bot is not running, CLI falls back to direct Claude Code invocation
- [ ] Session continuity: start conversation in Discord, continue from CLI (same context)
- [ ] Interactive CLI mode works (multi-turn conversation via socket)

### Non-Functional Requirements

- [ ] Latency: CLI → response should not add >100ms overhead vs direct invocation
- [ ] Reliability: stale socket cleanup on bot crash/restart
- [ ] No new external dependencies (asyncio has Unix socket support built-in)

## Dependencies & Risks

**Dependencies:**
- Bot must be running for unified session to work
- Unix domain sockets (macOS native, no issue)

**Risks:**
- **Bot down = degraded CLI.** Mitigated by fallback to direct invocation.
- **Concurrency.** CLI and Discord messages both go through the semaphore — CLI user may wait if Discord is processing. This is acceptable (same as today's Discord behavior).
- **Socket permissions.** Need to ensure the socket file is readable/writable by the CLI user. Same user, so no issue.
- **Long responses.** Streaming over Unix socket requires chunked reads. Asyncio handles this natively.

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `bot/ipc.py` | Create | Unix socket server, message routing, Discord posting |
| `bot/main.py` | Modify | Start IPC server in setup_hook, stop on shutdown |
| `cli/clawcode` | Modify | Add socket client mode, fallback logic |
| `scripts/schedule-runner.py` | Modify (Phase 4) | Route through socket instead of direct invocation |

## What This Does NOT Change

- Claude Code CLI is still the brain — bot still invokes it via `asyncio.create_subprocess_exec`
- Context cache system unchanged
- Session expiry logic unchanged
- Skill/memory system unchanged
- Discord bot behavior for Discord-native messages unchanged

## Future Considerations

- **Multi-channel CLI:** `clawcode --channel work` to target different Discord channels (different sessions)
- **Web UI:** Same IPC pattern could support a local web interface
- **Remote CLI:** Replace Unix socket with TCP for SSH-based access
