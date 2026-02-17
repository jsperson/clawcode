---
title: "feat: QMD unified search integration"
type: feat
date: 2026-02-16
---

# feat: QMD Unified Search Integration

## Overview

Replace ClawCode's keyword-only SQLite FTS5 search with QMD — a local hybrid search engine combining BM25 full-text search, semantic vector embeddings, and LLM re-ranking. QMD indexes markdown files and exposes an MCP server, giving Claude direct access to `qmd_search`, `qmd_query`, `qmd_get`, and `qmd_status` tools.

Index everything: Obsidian vault (~1,410 files), daily conversation logs (`memory/*.md`), and `MEMORY.md`. Keep FTS5 as fallback.

## Problem Statement

Current memory search (`bot/memory_search.py`) is keyword-only FTS5 over 11 files. It can't:
- Search the Obsidian vault (1,410 files, completely invisible to the bot)
- Understand semantic similarity ("deployment issues" won't find "rsync mistakes")
- Rank results by relevance beyond simple BM25 term frequency

When Claude needs past context, it either finds exact keyword matches or misses entirely.

## Proposed Solution

Install QMD, configure three collections, wire it in as an MCP server via `config/mcp-servers.yaml`, and schedule periodic re-indexing via launchd.

## Acceptance Criteria

- [x] QMD installed globally (`bun install -g @tobilu/qmd`)
- [x] Homebrew SQLite installed (`brew install sqlite` — required for FTS5 on macOS)
- [x] Three collections configured:
  - `vault` → `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott` (glob: `**/*.md`)
  - `daily-logs` → `~/clawcode/memory` (glob: `*.md`)
  - `memory` → `~/clawcode` (glob: `MEMORY.md`)
- [x] Initial indexing complete (`qmd update && qmd embed`)
- [x] QMD MCP server added to `config/mcp-servers.yaml`
- [x] Bot generates correct `.mcp-config.json` with QMD server on restart
- [x] Claude can call QMD tools (qmd_search, qmd_query, qmd_get, qmd_status)
- [x] Scheduled re-indexing via launchd plist (daily at 03:00)
- [x] `.claude/CLAUDE.md` updated with QMD-first search instructions
- [x] FTS5 search (`clawcode memory search`) preserved as fallback
- [x] QMD workspace (`~/.cache/qmd/`) excluded from ClawCode backup

## Technical Details

### QMD Installation

```bash
# Prerequisites
brew install sqlite          # macOS system sqlite lacks FTS5
# Bun already installed, or: curl -fsSL https://bun.sh/install | bash

# Install QMD
bun install -g @tobilu/qmd

# Verify
qmd --version
```

First run auto-downloads ~2GB of models to `~/.cache/qmd/models/`:
- EmbeddingGemma-300M (~300MB)
- Qwen3-Reranker-0.6B (~640MB)
- Query expansion model (~1.1GB)

### Collection Setup

```bash
# Add collections
qmd collection add ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/scott --name vault
qmd collection add ~/clawcode/memory --name daily-logs
qmd collection add ~/clawcode --name memory --mask "MEMORY.md"

# Initial index + embed (5-10 min for 1,410 files)
qmd update
qmd embed
```

### MCP Server Configuration

Add to `config/mcp-servers.yaml`:

```yaml
qmd:
  transport: stdio
  command: qmd
  args: ["mcp"]
  required_by: []
```

No env vars needed — QMD reads its collections from `~/.cache/qmd/index.sqlite`.

Bot auto-generates `.mcp-config.json` on startup via `bot/claude_bridge.py:_build_mcp_config()`.

### Available MCP Tools

| Tool | Purpose | When to use |
|------|---------|-------------|
| `qmd_search` | BM25 keyword search (fast) | Quick lookups, exact terms |
| `qmd_vsearch` | Vector semantic search | Conceptual/fuzzy queries |
| `qmd_query` | Hybrid BM25 + vector + LLM re-ranking (best quality) | Important queries, broad exploration |
| `qmd_get` | Retrieve full document by path or docid | After finding a result, read the full file |
| `qmd_multi_get` | Retrieve multiple documents | Batch file reads |
| `qmd_status` | Index health: collections, file counts, last update | Debugging, health checks |

Parameters: `query` (string), `limit` (default 10), `minScore` (default 0), `collection` (optional filter).

### Scheduled Re-indexing

Create `launchd/com.clawcode.qmd-reindex.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.clawcode.qmd-reindex</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>qmd update && qmd embed</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/jsperson/clawcode/data/logs/qmd-reindex.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/jsperson/clawcode/data/logs/qmd-reindex.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

### CLAUDE.md Search Instructions Update

Replace existing memory search section with:

```markdown
### Search

**Primary: QMD** (semantic + keyword search across vault, daily logs, and memory)
- Claude has direct access to QMD tools via MCP: `qmd_search`, `qmd_query`, `qmd_get`, `qmd_status`
- Use `qmd_search` for fast keyword lookups
- Use `qmd_query` for important queries needing semantic understanding
- Filter by collection: `collection: "vault"`, `collection: "daily-logs"`, `collection: "memory"`
- Use `qmd_get` to read full file content after finding relevant results

**Fallback: FTS5** (if QMD is unavailable)
- Run `clawcode memory search "<query>"` — keyword-only, covers MEMORY.md + daily logs
- Use `--source memory` for curated knowledge, `--source daily` for logs
```

## Implementation Checklist

### Phase 1: Install & Index
- [x] Install Homebrew SQLite: `brew install sqlite`
- [x] Install QMD: `bun install -g @tobilu/qmd`
- [x] Verify: `qmd --version`
- [x] Add vault collection
- [x] Add daily-logs collection
- [x] Add memory collection
- [x] Run `qmd update` (full-text index)
- [x] Run `qmd embed` (vector embeddings, 5-10 min)
- [x] Verify with `qmd status`
- [x] Test search: `qmd search "lawn care"`, `qmd query "deployment workflow"`

### Phase 2: MCP Integration
- [x] Add QMD server to `config/mcp-servers.yaml`
- [ ] Restart bot
- [ ] Verify `.mcp-config.json` includes QMD server
- [ ] Check bot logs for MCP server initialization
- [ ] Test QMD tools from a Claude session (search, query, get, status)

### Phase 3: Scheduled Re-indexing
- [x] Create `launchd/com.clawcode.qmd-reindex.plist`
- [x] Bootstrap plist: `launchctl bootstrap gui/$(id -u) launchd/com.clawcode.qmd-reindex.plist`
- [x] Test manually: `launchctl kickstart gui/$(id -u)/com.clawcode.qmd-reindex`
- [x] Verify log output in `data/logs/qmd-reindex.log`

### Phase 4: Documentation & Cleanup
- [x] Update `.claude/CLAUDE.md` search instructions
- [x] Update `HEARTBEAT.md.template` — add QMD index health check to lightweight scan
- [x] Add `~/.cache/qmd/` note to backup exclusions (models are re-downloadable)
- [x] Test FTS5 fallback still works independently

## Dependencies & Risks

- **Node.js ≥ 22 or Bun** — Bun is already installed on Mac Studio
- **Homebrew SQLite** — needed for FTS5 extension, may already be installed
- **~2GB model download** — one-time, needs stable internet
- **Initial embedding time** — 5-10 min for 1,410 files, blocks setup but not usage
- **No watch mode** — QMD doesn't auto-detect file changes. Daily re-index at 03:00 means up to 24h staleness for new content. Acceptable for vault; daily logs created throughout the day will be indexed next morning.
- **Concurrent access** — Multiple Claude processes (bot + CLI) each spawn their own `qmd mcp` stdio server. Each reads the same SQLite index. Concurrent reads are safe; re-indexing during search should be fine (SQLite WAL mode).

## References

- Brainstorm: `docs/brainstorms/2026-02-16-qmd-unified-search-brainstorm.md`
- QMD GitHub: https://github.com/tobi/qmd
- Existing MCP config: `config/mcp-servers.yaml`
- MCP config generator: `bot/claude_bridge.py:_build_mcp_config()`
- Current FTS5 search: `bot/memory_search.py`
- Existing search instructions: `.claude/CLAUDE.md` (Memory Search section)
