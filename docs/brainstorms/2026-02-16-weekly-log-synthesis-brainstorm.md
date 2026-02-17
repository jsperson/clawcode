---
topic: "Weekly Log Synthesis & Automation Pattern Detection"
date: 2026-02-16
status: complete
---

# Weekly Log Synthesis & Automation Pattern Detection — Brainstorm

## What We're Building

Enhance the heartbeat's weekly review to recognize behavioral patterns that Computer could automate. The current weekly review uses keyword searches against daily logs, which misses cross-day patterns. We need a two-layer system: daily summaries that compress raw conversation logs into structured artifacts, and a weekly review that reads those summaries to identify automation opportunities and produce proposals.

**Success looks like:** Computer posts a proposal to Discord saying "You asked me to check Canvas assignments 4 times this week — want me to add a proactive Canvas check to the morning digest?" or "You manually filed 3 notes to the vault this week using the same pattern — should I create a routing rule?"

## Why This Approach

### Daily Summaries + Weekly Review

Raw daily logs range from ~1KB (quiet days) to ~33KB (heavy days). A busy week could be 100-150KB across all log files. Rather than cramming raw logs into the weekly review's context, a morning task compresses yesterday's logs into a structured summary (~1-2KB). The weekly review reads 7 summaries — maybe 10KB total — and has plenty of context to think.

**Rejected alternatives:**
- **Piggyback on daily mini-review:** Couples two responsibilities, mini-review already has a tight time budget.
- **Weekly review reads raw logs directly:** Works on quiet weeks but risks context pressure on busy ones. Loses the daily summary artifact, which is useful on its own.

## Key Decisions

### 1. Morning summary as a scheduled task

Summary runs as a `schedules.yaml` entry (e.g., `daily_summary` at 06:30), covering the previous day's logs. This is a standalone scheduled task, not a heartbeat window — the heartbeat has no concept of "first cycle of the day" and adding one would be unnecessary complexity.

If yesterday has no log files (no `-discord.md` or `-cli.md`), skip silently. Some days have no activity.

### 2. Separate summary files

Write to `memory/YYYY-MM-DD-summary.md`. Raw logs (`-discord.md`, `-cli.md`) stay untouched as source of truth. Summaries are derived artifacts. Clean separation.

Note: CLI logs (`-cli.md`) are new and currently sparse — most days only have `-discord.md`. The summary task should handle either or both being present.

### 3. Narrative + key extractions

Each daily summary includes:
- **Narrative paragraph** — human-readable "what happened today" for quick scanning
- **Key extractions** for pattern matching:
  - Repeated requests or lookups
  - Manual tasks performed (things Computer could potentially automate)
  - Decisions made
  - Unresolved items / open threads

Start with these four. The weekly review will reveal which extractions are actually useful for pattern detection — add more only if needed.

### 4. Proposals only — no auto-implementation

When the weekly review spots an automation opportunity, it writes a formal proposal to `proposals/` and surfaces it to Discord. Computer never auto-implements. Scott approves or rejects. This keeps the trust model clean: Computer observes and proposes, Scott decides.

Prerequisite: `proposals/` directory must be created. It's referenced in HEARTBEAT.md but doesn't exist on disk yet.

### 5. Pattern detection categories

The weekly review looks for:
- **Repeated actions** — things Scott does manually more than twice a week
- **Repeated lookups** — information Scott asks for regularly that could be proactive
- **Workflow friction** — multi-step processes that could be streamlined
- **Missed automations** — things existing skills/tools could handle but aren't configured to

### 6. Time budgets preserved

- Morning summary: ~2-3 minutes (read logs, generate summary)
- Weekly review: stays at 10 minutes (read 7 summaries instead of raw logs)
- Both within existing constraints. No new heartbeat windows needed.

## Architecture

```
Daily (scheduled task, 06:30):
  Check if yesterday's -discord.md and/or -cli.md exist
  If neither exists → skip, no summary for that day
  Read available log files
  → Generate memory/YYYY-MM-DD-summary.md (narrative + extractions)

Weekly (existing Sunday 15:00-17:00 heartbeat window):
  Glob memory/*-summary.md for last 7 days
  Read available summaries (may be <7 if quiet days were skipped)
  → Identify patterns across the week
  → Write proposals to proposals/
  → Surface proposals to Discord
  → Write review summary to vault
```

## Implementation Steps

1. Create `proposals/` directory in the deployed instance
2. Add `daily_summary` entry to `schedules.yaml` with a prompt that reads yesterday's logs and writes the summary
3. Update the weekly review section of HEARTBEAT.md to read summaries instead of (or in addition to) running keyword searches
4. Run for 2-3 weeks, then evaluate: are the summaries useful? Are the right things being extracted? Adjust.

## Open Questions

1. **Summary prompt engineering:** What prompt produces the best daily summaries for pattern detection? Start with a simple template and refine based on what the weekly review actually uses.

2. **Backfill:** Generate summaries for existing log files retroactively, or start fresh? Starting fresh is simpler. Backfill only if the first weekly review feels starved for data.
