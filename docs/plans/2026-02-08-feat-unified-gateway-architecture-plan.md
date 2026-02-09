---
title: Unified Gateway Architecture
type: feat
date: 2026-02-08
---

# Unified Gateway Architecture

## Overview

Replace ClawCode's current direct-invocation architecture with a gateway process that sits between all interfaces (Discord bot, CLI TUI, schedule runner) and the Claude Code CLI. The gateway owns session management, claude process lifecycle, message routing, and conversation history. Discord bot and CLI become equal WebSocket clients. The core constraint: everything runs through the `claude` binary using a Max subscription — no API keys.

## Problem Statement

Today ClawCode has three disconnected interfaces:

1. **Discord bot** — rich session management (per-channel UUID, resume, persistence), concurrency control, context injection. Primary interface.
2. **CLI** (`clawcode`) — stateless. Every invocation is a fresh Claude Code call with no session continuity. Output only appears in the terminal.
3. **Schedule runner** — stateless. Posts output to Discord via REST but doesn't participate in sessions.

You can't start a conversation in Discord and continue it from the terminal. CLI work is invisible in Discord. There's no shared session state. The CLI loses Claude Code's native features (tool use, cancellation, streaming) because it runs in `--print` mode.

## Proposed Solution

A dedicated gateway process that:
- Manages long-running `claude` CLI subprocesses (one per session) using bidirectional JSON streaming
- Exposes a local WebSocket server for clients to connect
- Routes messages between clients and their `claude` sessions
- Persists session state across gateway restarts
- Pushes schedule output, lifecycle events, and notifications to all connected clients
- Shares memory, context, and skills across all interfaces

## Technical Approach

### Architecture

```
  launchd
    │
    ├── Gateway (Python, always running)
    │     ├── WebSocket server (ws://127.0.0.1:PORT)
    │     ├── Session manager (create, resume, expire, persist)
    │     ├── Claude process pool (spawn, stream, cancel, reap)
    │     ├── Context builder (identity + user + skills → system prompt)
    │     ├── Message router (client ↔ claude, broadcast)
    │     ├── Schedule executor (cron-triggered prompts)
    │     └── State store (SQLite WAL for sessions, history, state)
    │
    ├── Discord Bot (Python, connects as WS client)
    │     ├── Discord ↔ Gateway message bridge
    │     ├── Channel → session ID mapping
    │     ├── Message splitting (2000-char Discord limit)
    │     └── Lifecycle messages (online/offline dots)
    │
    └── CLI TUI (wraps claude interactive mode)
          ├── Connects to gateway for session assignment
          ├── Gateway spawns claude with allocated pty
          ├── TUI attaches to pty for full interactive experience
          └── Gateway intercepts I/O for logging + Discord mirroring
```

### TUI Architecture (Resolved Ambiguity)

The TUI uses a **hybrid model** — it connects to the gateway via WebSocket for session management and coordination, but the actual `claude` interactive process runs locally with a pty. The gateway:

1. Receives TUI connection via WebSocket
2. Assigns (or resumes) a session
3. Spawns a `claude` process with a pty allocated for that session
4. Returns pty file descriptor info to the TUI client
5. TUI attaches to the pty for full interactive `claude` experience (readline, colors, tool use, diffs)
6. Gateway taps the pty output for logging and optional Discord mirroring

This preserves all Claude Code features (the TUI literally IS claude's interactive mode) while letting the gateway track the session. The gateway doesn't mediate every keystroke — it manages the process lifecycle and taps the stream.

For Discord, the gateway uses the **JSON streaming model** (`--input-format=stream-json --output-format=stream-json --verbose`) since Discord messages are text-in/text-out with no interactive features needed.

### Claude Process Management

**Two modes per session type:**

| Interface | Claude Mode | Flags | Lifecycle |
|-----------|-------------|-------|-----------|
| Discord | JSON streaming | `--input-format=stream-json --output-format=stream-json --verbose --dangerously-skip-permissions` | Long-running, one process per session |
| CLI TUI | Interactive (pty) | `--dangerously-skip-permissions` + context injection | Long-running, one process per session |
| Schedule | JSON streaming | Same as Discord | Spawn per task, die after response |

**Process pool management:**
- Max concurrent `claude` processes: configurable (default 3) — each uses ~200-500 MB RAM
- Idle timeout: kill `claude` process after N minutes of inactivity (default 30 min, matching current session expiry)
- Orphan reaping: on gateway startup, scan for stale `claude` processes (by saved PID) and kill them
- Hang detection: no JSON output for 120s → kill and invalidate session
- Cancellation: SIGINT to claude process group (Esc in TUI, cancel command from Discord)

**Process group isolation:**
- Each `claude` subprocess runs in its own process group (`os.setpgrp()`)
- Gateway tracks PID and PGID per session
- On gateway shutdown: SIGTERM to all child process groups

### Wire Protocol (Gateway ↔ Clients)

WebSocket messages are newline-delimited JSON:

**Client → Gateway:**
```json
{"type": "auth", "token": "<shared_secret>"}
{"type": "message", "session_id": "uuid", "content": "what events do I have tomorrow?"}
{"type": "session.create", "client_type": "discord", "metadata": {"channel_id": "123"}}
{"type": "session.resume", "session_id": "uuid"}
{"type": "cancel", "session_id": "uuid"}
```

**Gateway → Client:**
```json
{"type": "auth.ok", "client_id": "uuid"}
{"type": "session.created", "session_id": "uuid"}
{"type": "chunk", "session_id": "uuid", "content": "partial response text..."}
{"type": "response", "session_id": "uuid", "content": "full response text"}
{"type": "error", "session_id": "uuid", "code": "timeout", "message": "Claude process timed out"}
{"type": "push", "source": "schedule", "task": "daily_digest", "content": "..."}
{"type": "lifecycle", "event": "gateway.starting"}
```

**Client types** identified on auth: `discord`, `tui`, `schedule`, `oneshot`.

### Session Management

**Session data model** (SQLite WAL, not JSON files):

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,           -- UUID
    client_type TEXT NOT NULL,     -- discord, tui, schedule
    client_metadata TEXT,          -- JSON: channel_id, etc.
    claude_session_id TEXT,        -- Claude CLI's internal session ID
    claude_pid INTEGER,            -- PID of claude process (NULL if not running)
    created_at REAL NOT NULL,      -- time.time()
    last_activity REAL NOT NULL,
    message_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'   -- active, idle, expired
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,            -- user, assistant
    content TEXT NOT NULL,
    source TEXT,                   -- discord, tui, schedule
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

**Session lifecycle:**
1. Client connects → authenticates → creates or resumes session
2. Gateway spawns `claude` process (or reattaches to existing)
3. Messages flow bidirectionally
4. On idle timeout: kill `claude` process, mark session as idle (can resume later via `--resume`)
5. On expiry (configurable, default 2 hours): mark session as expired, free resources
6. On client disconnect: keep `claude` process alive for reconnection window (5 min)

**Reconnection:**
- Client reconnects → resumes session → receives message history since disconnect
- If `claude` process died during disconnect → error event, client must create new session

### Context & Memory Integration

**Context injection:**
- Built once by context builder (same as current `bot/context.py`)
- Passed to `claude` at process spawn time via `--append-system-prompt`
- File watcher monitors IDENTITY.md, USER.md, SKILL.md for changes
- On context change: log a warning, do NOT kill active sessions (accept stale context within a session)
- New sessions get fresh context automatically

**Memory writes:**
- Gateway is the authoritative writer to MEMORY.md and daily logs
- `claude` subprocesses write via their normal tool use (bash, file edit) — these go through the pty/stdin
- File locking via `fcntl.flock()` remains for MEMORY.md writes
- Memory search index (SQLite FTS5): gateway triggers re-index after memory writes, using existing lazy mtime-based approach

**Shared state files:**
- `data/gateway.db` — sessions, messages, state (replaces `sessions.json` and `state.json`)
- `data/context.cache` — compiled system prompt (unchanged)
- `data/memory.db` — FTS5 search index (unchanged)

### Schedule Integration

Schedule runner is absorbed into the gateway:

- Gateway reads `config/schedules.yaml` at startup
- Uses asyncio-based cron scheduler (replaces launchd per-task plists)
- When a schedule fires:
  1. Spawn a one-shot `claude` process with the task prompt
  2. Collect response
  3. Push to all connected clients (Discord bot posts to channel, TUI shows notification)
  4. Log result to `data/gateway.db`
- If gateway is down when schedule should fire: launchd's `KeepAlive` ensures quick restart, schedules catch up via "missed execution" check on startup

**Fallback:** Keep `scripts/schedule-runner.py` functional as a standalone fallback. If the gateway is down for extended maintenance, launchd can fire the runner directly.

### Security

- **Local-only binding:** WebSocket server binds to `127.0.0.1` only, never `0.0.0.0`
- **Shared secret auth:** Token loaded from `.env` (`GATEWAY_TOKEN=<random>`), validated on WebSocket handshake
- **Unix domain socket option:** Support `data/gateway.sock` as alternative to TCP WebSocket (filesystem permissions for access control)
- **Process isolation:** Each `claude` process in its own process group
- **`--dangerously-skip-permissions`:** Applied per-session, configurable (Discord sessions always skip, TUI sessions optionally prompt)

### Configuration

New `gateway:` section in `config/config.yaml`:

```yaml
gateway:
  host: 127.0.0.1
  port: 7429                        # CLWC on phone keypad
  socket_path: data/gateway.sock    # Unix socket alternative (preferred)
  max_sessions: 5
  max_claude_processes: 3
  session_idle_timeout_minutes: 30
  session_expiry_minutes: 120
  reconnect_window_minutes: 5
  claude_hang_timeout_seconds: 120
  log_level: INFO
```

### Implementation Phases

#### Phase 1: Gateway Core + Discord Migration

Build the gateway process with claude process management and WebSocket server. Migrate the Discord bot from direct claude invocation to gateway client.

**Tasks:**
- [ ] Create `gateway/` Python package
- [ ] `gateway/server.py` — asyncio WebSocket server (using `websockets` library)
- [ ] `gateway/sessions.py` — session manager with SQLite WAL storage
- [ ] `gateway/claude_pool.py` — claude process pool (spawn, stream, cancel, reap)
- [ ] `gateway/router.py` — message routing between clients and claude processes
- [ ] `gateway/protocol.py` — wire protocol message types and serialization
- [ ] `gateway/scheduler.py` — asyncio cron scheduler (absorbs schedule-runner)
- [ ] `gateway/main.py` — entry point, signal handling, graceful shutdown
- [ ] `gateway/config.py` — gateway-specific config loading
- [ ] Modify `bot/main.py` — replace `ClaudeBridge.invoke()` with gateway WebSocket client
- [ ] Create `bot/gateway_client.py` — WebSocket client for bot → gateway communication
- [ ] Add `gateway:` section to `config/config.yaml`
- [ ] Create `launchd/com.clawcode.gateway.plist`
- [ ] Update `scripts/install.sh` — install gateway service
- [ ] Add `websockets` to `pyproject.toml` dependencies
- [ ] Update `clawcode doctor` — add gateway health check

**Success criteria:**
- [ ] Gateway starts via launchd, stays running
- [ ] Discord bot connects to gateway, sends messages, receives responses
- [ ] Discord messages use long-running claude processes (not one-shot `--print`)
- [ ] Session persistence across gateway restart
- [ ] `clawcode doctor` reports gateway health

**Estimated effort:** Large — this is the core infrastructure.

#### Phase 2: CLI TUI

Build the TUI client that wraps claude's interactive mode via the gateway.

**Tasks:**
- [ ] Create `cli/tui.py` — TUI client that connects to gateway, attaches to pty
- [ ] `gateway/pty_manager.py` — allocate and manage ptys for TUI sessions
- [ ] Modify `cli/clawcode` — add `tui` subcommand that launches TUI client
- [ ] Push message display in TUI (schedule output, lifecycle events)
- [ ] Session resume on TUI reconnect
- [ ] Graceful disconnect (Ctrl-D to detach, session stays alive)

**Success criteria:**
- [ ] `clawcode tui` opens interactive claude session through gateway
- [ ] Full Claude Code experience (tool use, file editing, diffs, cancellation)
- [ ] Push messages appear in TUI
- [ ] Session survives TUI disconnect/reconnect

**Estimated effort:** Medium — pty management is the tricky part.

#### Phase 3: Schedule Absorption + One-Shot CLI

Absorb the schedule runner into the gateway and add a one-shot CLI mode that routes through the gateway.

**Tasks:**
- [ ] `gateway/scheduler.py` — read `config/schedules.yaml`, run cron schedules
- [ ] Push schedule output to all connected clients
- [ ] Modify `cli/clawcode` — one-shot mode routes through gateway (fallback to direct if gateway down)
- [ ] Remove per-schedule launchd plists (gateway handles scheduling internally)
- [ ] Update `scripts/schedule-sync.py` — sync to gateway config instead of launchd plists
- [ ] Missed execution catch-up on gateway startup

**Success criteria:**
- [ ] Schedules fire through gateway, output appears in Discord and TUI
- [ ] `clawcode "question"` routes through gateway when available
- [ ] Fallback to direct invocation when gateway is down
- [ ] No per-schedule launchd plists needed

**Estimated effort:** Small-medium — builds on Phase 1 infrastructure.

#### Phase 4: Polish + Observability

**Tasks:**
- [ ] `clawcode gateway status` — show active sessions, claude processes, connected clients
- [ ] Structured logging with session correlation IDs
- [ ] Log rotation (newsyslog or size-capped)
- [ ] `/deliver` toggle — control whether TUI responses also post to Discord
- [ ] Session history query — "what happened while I was offline?"
- [ ] `clawcode gateway restart` — graceful restart command

**Success criteria:**
- [ ] Full operational visibility into gateway state
- [ ] Clean log output with traceability
- [ ] Cross-interface awareness (TUI can see Discord history)

**Estimated effort:** Small — incremental improvements.

## Alternative Approaches Considered

### Bot as Gateway (Rejected)
The Discord bot becomes the gateway, and CLI connects to it. Rejected because:
- CLI loses Claude Code's native features (interactive tool use, cancellation)
- Bot failure degrades CLI
- Tight coupling between Discord-specific code and session management
- See superseded plan: `docs/plans/2026-02-08-feat-unified-cli-discord-session-plan.md`

### API-Based Gateway (Not Applicable)
Like OpenClaw's pattern — gateway calls Anthropic API directly. Not applicable because ClawCode uses Claude Code CLI with Max subscription, no API keys. The gateway must manage `claude` subprocesses, not API calls.

### Pure CLI Wrapping (Insufficient)
Just wrap `claude` CLI in a script with session tracking. Doesn't solve: Discord integration, push notifications, shared sessions, schedule routing.

## Acceptance Criteria

### Functional Requirements

- [ ] Gateway process starts via launchd, stays running with KeepAlive
- [ ] Discord bot connects to gateway and sends/receives messages
- [ ] CLI TUI provides full interactive Claude Code experience through gateway
- [ ] Schedule tasks fire through gateway, output pushes to all clients
- [ ] Sessions persist across gateway restarts
- [ ] One-shot CLI routes through gateway with fallback to direct invocation
- [ ] Shared memory and context across all interfaces
- [ ] Session resume after client disconnect/reconnect

### Non-Functional Requirements

- [ ] Latency: <100ms overhead for message routing (gateway ↔ client)
- [ ] Memory: <500 MB per claude process, <100 MB for gateway itself
- [ ] Max concurrent sessions: configurable (default 5)
- [ ] Uptime: launchd KeepAlive ensures automatic restart on crash
- [ ] Security: local-only binding, shared secret auth on WebSocket

### Quality Gates

- [ ] Integration tests for WebSocket connection, session lifecycle, claude process management
- [ ] Migration test: verify Discord bot works with both old (direct) and new (gateway) modes
- [ ] Stress test: concurrent Discord + TUI sessions
- [ ] Fallback test: verify CLI works when gateway is down

## Dependencies & Prerequisites

**Runtime:**
- Python 3.13+ (current)
- `websockets` library (new dependency)
- Claude Code CLI with streaming support (`--input-format=stream-json --output-format=stream-json`)

**External:**
- Claude Code CLI version that supports bidirectional JSON streaming
- Max subscription active

**Risks:**
- **Claude CLI streaming interface stability:** These flags may change in future Claude Code updates. Pin or check CLI version at startup.
- **Max subscription rate limits:** Unpublished. Multiple concurrent claude processes may hit limits. Mitigate with configurable process pool cap and backoff.
- **Pty management complexity:** Allocating and managing ptys for TUI sessions adds OS-level complexity. Use Python's `pty` module, test thoroughly on macOS.
- **Migration disruption:** Running old bot and new gateway simultaneously risks duplicate Discord responses. Use feature flag to cut over cleanly.

## Migration Path

1. **Build gateway (Phase 1)** with Discord client support
2. **Feature flag in bot:** `use_gateway: true` in config — when true, bot routes through gateway instead of direct claude invocation
3. **Test:** Run gateway + bot with flag enabled, verify identical behavior
4. **Cut over:** Enable flag, remove direct invocation code path from bot
5. **Phase 2-4:** Add TUI, absorb schedules, polish
6. **Cleanup:** Remove old `ClaudeBridge` direct invocation code, old schedule launchd plists

**Rollback:** Disable `use_gateway` flag, bot reverts to direct invocation. Gateway can be stopped without affecting bot functionality.

## Files to Create

| File | Description |
|------|-------------|
| `gateway/__init__.py` | Package init |
| `gateway/main.py` | Entry point, signal handling, graceful shutdown |
| `gateway/server.py` | Asyncio WebSocket server |
| `gateway/sessions.py` | Session manager with SQLite WAL |
| `gateway/claude_pool.py` | Claude process pool management |
| `gateway/pty_manager.py` | Pty allocation for TUI sessions |
| `gateway/router.py` | Message routing (client ↔ claude) |
| `gateway/protocol.py` | Wire protocol types and serialization |
| `gateway/scheduler.py` | Asyncio cron scheduler |
| `gateway/config.py` | Gateway config loading |
| `bot/gateway_client.py` | WebSocket client for bot → gateway |
| `cli/tui.py` | TUI client (pty attachment) |
| `launchd/com.clawcode.gateway.plist` | launchd agent for gateway |

## Files to Modify

| File | Change |
|------|--------|
| `bot/main.py` | Add gateway client mode (feature flagged) |
| `bot/claude_bridge.py` | Keep as fallback, add gateway routing option |
| `cli/clawcode` | Add `tui` and `gateway` subcommands, route one-shot through gateway |
| `config/config.yaml` | Add `gateway:` section |
| `scripts/install.sh` | Install gateway launchd agent, add `websockets` dep |
| `scripts/doctor.py` | Add gateway health check |
| `pyproject.toml` | Add `websockets` dependency |
| `.env` template | Add `GATEWAY_TOKEN` |

## What Stays the Same

- Skills system (`skills/*/SKILL.md`, `skills/loader.py`)
- Memory system (MEMORY.md, daily logs, `bot/memory_search.py`)
- Context builder (`bot/context.py`) — reused by gateway
- Config system (`config/config.yaml`, `config/schedules.yaml`)
- Doctor (`scripts/doctor.py`) — extended, not replaced
- Install process (`scripts/install.sh`) — extended, not replaced
- CLI subcommands (`doctor`, `skill`, `schedule`, `memory`) — unchanged

## References

- Brainstorm: `docs/brainstorms/2026-02-08-unified-gateway-architecture-brainstorm.md`
- Superseded plan: `docs/plans/2026-02-08-feat-unified-cli-discord-session-plan.md`
- Current session management: `bot/claude_bridge.py`
- Current CLI wrapper: `cli/clawcode`
- Current schedule runner: `scripts/schedule-runner.py`
- OpenClaw gateway pattern: `~/openclaw/` (reference implementation)
