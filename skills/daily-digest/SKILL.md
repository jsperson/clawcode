---
name: daily-digest
description: Generate daily digest with tasks, calendar, projects, and Canvas data
triggers:
  - daily digest
  - morning digest
  - generate digest
  - run digest
metadata:
  clawcode:
    requires:
      bins:
        - remindctl
        - icalpal
        - jq
---

# Daily Digest

Generates a comprehensive daily digest and saves it to the Obsidian vault.

## What It Does

Runs `scripts/daily-digest.sh` which collects:
- **Tasks** from Apple Reminders (overdue, due today, all active by list)
- **Calendar** events for today via icalpal
- **Project** files modified in last 24 hours
- **Canvas** LMS data (grades, assignments, discussions, announcements)

Output:
- Writes full digest to `Digests/Daily/YYYY-MM-DD.md` in the Obsidian vault
- Copies to `Digests/Today.md` for quick access
- Prints summary to stdout (for Discord when run via scheduler)

## Usage

Run manually:
```bash
bash ~/clawcode/scripts/daily-digest.sh
```

Scheduled via `config/schedules.yaml` as `daily_digest` (07:00 daily).

## Dependencies

- `remindctl` — Apple Reminders CLI
- `icalpal` — macOS Calendar CLI
- `jq` — JSON processor
- `canvasapi` Python package — Canvas LMS integration (optional)
- Canvas token at `~/.config/canvas/token` (optional)
