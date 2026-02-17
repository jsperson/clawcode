---
title: "feat: Daily Log Summary + Enhanced Weekly Synthesis"
type: feat
date: 2026-02-16
brainstorm: docs/brainstorms/2026-02-16-weekly-log-synthesis-brainstorm.md
---

# Daily Log Summary + Enhanced Weekly Synthesis

## Overview

Add a daily summarization task that compresses raw conversation logs into structured summaries, and enhance the weekly review to read those summaries for automation pattern detection. The goal: Computer spots what Scott does repeatedly and proposes automations.

## Problem Statement

The weekly review currently keyword-searches raw daily logs via `clawcode memory search`. This finds specific terms but misses cross-day behavioral patterns — the kind of insight that reveals automation opportunities. Raw logs are too large to feed directly into the weekly review's context window (busy weeks: 100-150KB across all files). A compression layer is needed.

## Proposed Solution

Two components:

1. **Daily summary task** — scheduled at 06:30, reads yesterday's logs, writes a structured summary
2. **Enhanced weekly review** — reads 7 summaries instead of keyword-searching raw logs, focuses on pattern detection

### Architecture

```
Daily (schedules.yaml, 06:30):
  Glob memory/YYYY-MM-DD-*.md for yesterday (excluding *-summary.md)
  Skip if no files or combined content < 200 chars (beyond headers)
  Read available log files
  → Write memory/YYYY-MM-DD-summary.md

Weekly (existing Sunday 15:00-17:00 heartbeat):
  Glob memory/*-summary.md for last 7 days
  Read available summaries (may be <7 if quiet days skipped)
  → Identify automation patterns
  → Write proposals to proposals/
  → Surface to Discord + vault
  (All other scan sources remain: git, skills, config, vault activity)
```

## Technical Approach

### 1. Daily Summary Task (`schedules.yaml` entry)

**Execution mode:** `prompt` — Claude CLI reads logs and writes the summary file.

**Scheduling:** `cron: "30 6 * * *"` (06:30 daily). After QMD reindex (03:00), before first heartbeat cycle.

**Context:** Minimal. The summary task is data extraction, not a conversational response. No need for full identity/personality context. Just the prompt with explicit instructions.

**Discord output:** One-line confirmation: "Daily summary written for YYYY-MM-DD" or "No activity to summarize for YYYY-MM-DD." Keeps the channel clean.

**Log file discovery:** Glob `memory/YYYY-MM-DD-*.md` excluding `*-summary.md`. Forward-compatible if new log sources appear later.

**Minimum content threshold:** Skip if combined non-header content is under 200 characters. Empty template files (just headers, no entries) are not worth summarizing.

**Backfill:** On each run, check previous 3 days for missing summaries. If yesterday has no summary, generate it. If day-before-yesterday has no summary and a log exists, generate that too. Keeps gaps from accumulating without unbounded backfill.

**File locking:** Not needed. The summary task writes to yesterday's `*-summary.md`. The bot writes to today's `*-discord.md`. No concurrent access.

**Time budget:** 2-3 minutes including Claude CLI startup. The prompt should enforce this.

### 2. Summary File Format

`memory/YYYY-MM-DD-summary.md`:

```markdown
---
date: YYYY-MM-DD
sources:
  - YYYY-MM-DD-discord.md
  - YYYY-MM-DD-cli.md
entries: 14
time_span: "08:15 - 22:30"
---

# YYYY-MM-DD Summary

## Narrative

One paragraph describing what happened. What was Scott working on?
What topics came up? What was the overall flow of the day?

## Repeated Requests

- Items Scott asked for multiple times or that echo previous days
- Lookups, checks, queries that feel habitual

## Manual Tasks

- Things Scott did by hand that Computer could potentially automate
- Multi-step workflows, file management, routine operations

## Decisions Made

- Choices, preferences expressed, directions set
- Technical decisions, project directions, schedule commitments

## Unresolved Items

- Open questions, things to follow up on
- Tasks mentioned but not completed
- Ideas floated but not acted on
```

### 3. Enhanced Weekly Review (HEARTBEAT.md update)

**What changes:** The weekly review's "Pattern Scan" step replaces `clawcode memory search` with reading the last 7 summary files. All other scan sources remain unchanged (git history, skills rotation, config, vault activity, HEARTBEAT.md self-review).

**New pattern detection categories** (added to weekly review instructions):
- **Repeated actions** — things Scott does manually more than twice a week
- **Repeated lookups** — information asked for regularly that could be proactive
- **Workflow friction** — multi-step processes that could be streamlined
- **Missed automations** — things existing skills/tools could handle but aren't configured to

**Explicit instructions for the weekly review prompt:**

```
Read the last 7 daily summaries from memory/*-summary.md.
Look across the week for patterns:
- What did Scott ask for repeatedly? Could it be proactive?
- What manual tasks appeared multiple times? Could they be automated?
- What workflows took multiple steps? Could they be streamlined?
- What existing skills or tools could handle something Scott did manually?

For each pattern found, write a proposal to proposals/ following the
standard format. Every weekly review MUST produce at least one proposal,
memory update, or standing order change.
```

### 4. Daily Summary Prompt

The prompt for `schedules.yaml`:

```
You are a log summarizer. Read yesterday's conversation logs and produce a structured summary.

INSTRUCTIONS:
1. Calculate yesterday's date
2. Look for files matching memory/YYYY-MM-DD-*.md for yesterday (exclude *-summary.md)
3. If no files exist or content is trivially short (just headers), respond with: "No activity to summarize for YYYY-MM-DD"
4. Also check the previous 2 days for missing *-summary.md files — if logs exist but no summary, generate those too (oldest first)
5. For each day that needs a summary, read all matching log files and write memory/YYYY-MM-DD-summary.md

SUMMARY FORMAT:
Write the file with this exact structure:
- YAML frontmatter: date, list of source files, entry count, time span
- ## Narrative: One paragraph, 3-5 sentences. What was Scott working on? What topics came up?
- ## Repeated Requests: Bullet list. Things asked for multiple times or echoing previous patterns.
- ## Manual Tasks: Bullet list. Things done by hand that could be automated.
- ## Decisions Made: Bullet list. Choices, preferences, directions set.
- ## Unresolved Items: Bullet list. Open questions, incomplete tasks, ideas not acted on.

If a section has nothing, write "None" — don't omit the section.

Keep each summary concise. Time budget: 2-3 minutes total including all backfill days.
```

## Files to Create/Modify

### New files

| File | Description |
|------|-------------|
| `config/schedules.yaml` (entry) | Add `daily_summary` scheduled task |

### Modified files (all in `~/source/clawcode`)

| File | Change |
|------|--------|
| `config/schedules.yaml` | Add `daily_summary` entry with cron and prompt |
| `HEARTBEAT.md.template` | Update weekly review section to read summaries and detect patterns |
| `~/clawcode/HEARTBEAT.md` | Re-seed or manually update the weekly review section |

### Runtime files (created automatically)

| File | Description |
|------|-------------|
| `memory/YYYY-MM-DD-summary.md` | Daily summary (one per active day) |
| `proposals/*.md` | Proposals generated by weekly review |

## Acceptance Criteria

- [ ] `daily_summary` entry in `schedules.yaml` with correct cron (06:30 daily)
- [ ] Running `schedule-runner.py daily_summary` produces a summary file for yesterday
- [ ] Summary file matches the defined format (frontmatter + 5 sections)
- [ ] Days with no logs produce a skip message, no summary file
- [ ] Days with trivial content (< 200 chars beyond headers) are skipped
- [ ] Backfill: missing summaries for past 3 days are generated on each run
- [ ] `schedule-sync.py` creates the launchd plist for the new task
- [ ] HEARTBEAT.md.template weekly review section updated with summary-reading instructions
- [ ] Deployed HEARTBEAT.md updated to match
- [ ] Weekly review reads summaries and produces at least one proposal/update
- [ ] Discord receives one-line confirmation after daily summary runs

## Dependencies & Risks

**Dependencies:**
- `schedule-sync.py` must be run after adding the schedules.yaml entry
- Deployed `HEARTBEAT.md` must be updated (it's self-modifying, so manual seed or careful edit)

**Risks:**
- **Prompt quality:** Summary quality depends entirely on the prompt. Plan to iterate after seeing first outputs.
- **Context pressure:** Very large log days (30KB+) might stress the 2-3 minute budget. The backfill-3-days feature could compound this.
- **First weekly review:** Will have at most 7 summaries. The review should gracefully handle fewer.

## Implementation Steps

1. Add `daily_summary` to `config/schedules.yaml`
2. Run `schedule-sync.py` to install the launchd agent
3. Test manually: `schedule-runner.py daily_summary` — verify summary output
4. Update `HEARTBEAT.md.template` weekly review section
5. Update deployed `~/clawcode/HEARTBEAT.md` weekly review section
6. Deploy changed files from source to live
7. Wait for first Sunday review cycle to validate the full loop

## Evaluation

After 2-3 weeks:
- Are summaries useful? Do they capture the right information?
- Is the weekly review producing proposals? Are they relevant?
- Are the structured extractions the right ones, or do we need to add/remove fields?
- Is the 06:30 timing right, or should it be earlier/later?
- Adjust prompt and format based on findings.

## References

- Brainstorm: `docs/brainstorms/2026-02-16-weekly-log-synthesis-brainstorm.md`
- Phase 3 plan: `docs/plans/2026-02-16-feat-phase-3-autonomous-actions-plan.md`
- Heartbeat template: `HEARTBEAT.md.template`
- Schedule runner: `scripts/schedule-runner.py`
- Schedule config: `config/schedules.yaml`
- Bot heartbeat code: `bot/main.py:656` (`_build_heartbeat_prompt`)
