# Capability Scouting & Self-Experimentation — Brainstorm

**Date:** 2026-02-22
**Status:** Ready for planning

## What We're Building

A system where ClawCode proactively scouts for new AI agent capabilities from external sources (Reddit, HN, etc.), experiments with promising finds in a Docker sandbox, and reports results to Scott via Discord. The goal: ClawCode evolves itself by discovering what's possible, not just executing what's asked.

**This is NOT life coaching.** The Life Agent handles Scott's habits, health, and priorities. This is about ClawCode's own continuous improvement — finding new tricks, testing them, and surfacing the ones worth wiring in.

## Why This Approach

- **The AI agent space moves fast.** People in the OpenClaw community and beyond are adding new capabilities daily. ClawCode should be watching and learning, not waiting to be told what to build.
- **Scout-Experiment-Report balances autonomy with control.** ClawCode gets a sandbox (Docker) to try things freely. Scott gets Discord pings with results. Nothing ships to production without Scott's say-so.
- **Start narrow, expand based on signal.** Begin with 2-3 high-signal sources. Add more only when we know what produces value vs. noise.

## Key Decisions

1. **Scope: ClawCode self-improvement, not life optimization.** The heartbeat stays lean. This is a new capability, not an expansion of existing heartbeat standing orders.
2. **Architecture: expand the overnight cycle (daily) + weekly deep dive.** Daily lightweight scouting runs as part of or alongside the overnight cycle. Weekly synthesis picks the best finds for deeper examination.
3. **Experimentation: Docker sandbox on the host.** Full autonomy inside the container — install tools, run code, test MCP servers. Nothing touches the host until Scott approves.
4. **Output: Discord messages.** Quick conversational pings: what was found, what was tried, what worked. No vault write-ups unless Scott asks for detail.
5. **Sources: start narrow (2-3), expand.** Initial set TBD during planning — likely r/ClaudeAI, r/LocalLLaMA or similar, and one more high-signal source.
6. **Guardrails: sandbox boundary is sacred.** ClawCode can do anything inside Docker. Outside Docker, existing proposal/approval pipeline applies for any production changes.

## Open Questions

None — all resolved during brainstorm.

## Resolved Questions

1. **Which 2-3 sources to start with?** Decide during planning. Evaluate signal-to-noise. Web search is the access method for all sources.
2. **Docker setup?** Docker Desktop installed and running on the Mac Studio. Bot access TBD but Docker CLI is available.
3. **Daily scouting budget?** Quick scan — ~5 minutes, ~10 web searches. Deep dives are weekly only.
4. **How does ClawCode access sources?** Web search + WebFetch for everything. No API keys needed. X/Twitter is best-effort via web search.
5. **What makes a find "worth experimenting with"?** Define heuristics during planning — applicable to ClawCode's stack, achievable in a sandbox session, not already something we do.
