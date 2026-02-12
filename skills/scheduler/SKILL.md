---
name: scheduler
description: Manage recurring scheduled tasks — add, modify, remove, enable, disable
  schedules. Use when user mentions "schedule", "cron", "recurring", "timer",
  "every day", "every hour", "every morning", "automated", "periodic",
  "remind me every", "run daily", "run weekly", or similar scheduling requests.
metadata:
  clawcode:
    emoji: "🕐"
    os: ["darwin"]
    requires:
      bins: [launchctl]
---

# Scheduler (launchd)

Schedules are managed as macOS launchd agents. The source of truth is `config/schedules.yaml`.

## CRITICAL: Always Complete the Full Workflow

When the user asks to schedule something, you MUST do all three steps — no exceptions, no asking, no partial work:

1. **Read** current schedules: `config/schedules.yaml`
2. **Edit** the YAML to add, modify, remove, or enable/disable the task
3. **Run** `python3 ~/clawcode/scripts/schedule-sync.py` to push changes to launchd

Editing the YAML alone does nothing until sync runs. Never create standalone launchd plists — everything goes through `schedules.yaml` and the sync script. If the user says "schedule X at Y time," that means: add it to the YAML and sync it. Done.

## YAML Format

```yaml
schedules:
  task_name:
    cron: "0 8 * * *"       # 5-field cron: min hour dom month dow
    prompt: "What to tell Claude Code"
    enabled: true            # set false to disable without deleting
```

## Cron Syntax

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, 0=Sunday)
│ │ │ │ │
* * * * *
```

Examples:
- `0 8 * * *` — daily at 08:00
- `0 8 * * 1-5` — weekdays at 08:00
- `*/30 * * * *` — every 30 minutes
- `0 18 * * *` — daily at 18:00
- `0 16 * * 0` — Sundays at 16:00
- `0 9,12,17 * * *` — at 09:00, 12:00, and 17:00

## Examples

### Add a new schedule

```yaml
  standup_prep:
    cron: "30 8 * * 1-5"
    prompt: "Prepare standup notes: yesterday's completed items, today's plan, blockers"
    enabled: true
```

### Disable a schedule

Set `enabled: false` — the sync will remove its launchd agent.

### Remove a schedule

Delete the entry from the YAML, then sync.

## CLI Commands

- `clawcode schedule sync` — push YAML changes to launchd
- `clawcode schedule list` — show schedules with status
- `clawcode schedule logs <name>` — tail a schedule's log

## How It Works

- Each enabled schedule becomes a macOS launchd agent (`com.clawcode.schedule.<name>`)
- launchd triggers `scripts/schedule-runner.py <name>` at the scheduled time
- The runner invokes Claude Code CLI with the task's prompt
- Results are posted to the configured Discord channel
- Logs go to `data/logs/schedule-<name>.log`

## Important Notes

- Schedules run independently of the Discord bot — if the bot is down, schedules still fire
- All times are in the system timezone (America/Chicago)
- The sync is idempotent: it removes all existing agents and recreates from YAML
- After any edit to schedules.yaml, always run the sync script
