---
topic: QMD Unified Search Integration
date: 2026-02-16
status: complete
---

# QMD Unified Search Integration

## What We're Building

Replace ClawCode's keyword-only search with QMD — a local hybrid search engine that combines BM25 full-text search with semantic vector search and LLM re-ranking. QMD indexes markdown files and exposes an MCP server, making it a natural fit.

**Scope:** Index everything — Obsidian vault (~1,410 markdown files), daily conversation logs (`memory/*.md`), and `MEMORY.md` — into QMD as the primary search backend. Expose via MCP server so Claude can call `qmd_search`, `qmd_deep_search`, etc. directly.

## Why This Approach

**Current pain points:**
- Memory search is keyword-only (SQLite FTS5) — no semantic understanding
- Obsidian vault (1,410 files, 2.8GB) is completely unsearchable by the bot
- When Claude needs past context, it either finds exact keyword matches or misses entirely
- No way to ask "what did we discuss about deployment workflows" and get semantically relevant results

**What QMD gives us:**
- Hybrid BM25 + vector search with LLM re-ranking
- Built-in MCP server (`qmd mcp`) — direct tool access for Claude
- Multiple collections — can separate vault, daily logs, memory
- Fully local — no data leaves the machine
- ~2GB model download, runs on Mac Studio easily

## Key Decisions

1. **Unified search via QMD MCP server** — Claude calls QMD tools directly (qmd_search, qmd_deep_search, qmd_query, qmd_get). No CLI wrapper needed.

2. **Index everything** — Three collections:
   - `vault` → Obsidian vault (`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott`)
   - `daily-logs` → conversation history (`~/clawcode/memory/*.md`)
   - `memory` → curated knowledge (`~/clawcode/MEMORY.md`)

3. **Keep FTS5 as fallback** — Don't remove `memory_search.py` or `clawcode memory search`. QMD is primary, FTS5 is backup if QMD is down or during initial migration.

4. **MCP server in mcp-servers.yaml** — Add QMD alongside gmail-mcp and playwright. Bot auto-generates the config on startup.

## QMD Setup Summary

- Install: `npm install -g @tobilu/qmd` (requires Node.js ≥ 22)
- macOS needs: `brew install sqlite` (for extension support)
- First run downloads ~2GB of models (embedding-gemma-300M, re-ranker)
- Collections: `qmd collection add <path> --name <name>`
- Index: `qmd update` (full-text) + `qmd embed` (vectors)
- MCP: `qmd mcp` (stdio) or `qmd mcp --http` (HTTP)

## Open Questions

- **Index refresh:** How often should we re-index? Daily via scheduler? On file change? QMD may have watch mode.
- **Collection filtering:** Should Claude search all collections by default, or should skills specify which collection to search?
- **Vault size:** 2.8GB vault — how long does initial indexing + embedding take? Need to test.
- **CLAUDE.md update:** Need to update memory search instructions to prefer QMD tools over `clawcode memory search`.
- **Embedding model size:** ~2GB total model download — fine for Mac Studio, but worth noting.
