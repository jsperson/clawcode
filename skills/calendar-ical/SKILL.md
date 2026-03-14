---
name: calendar
description: Query and manage macOS Calendar events via CLI. Use when user asks about
  "calendar", "events", "schedule", "meetings", "what's on my calendar",
  "what do I have today", "next meeting", "free time", or "create an event".
allowed-tools: Bash(ical:*)
metadata:
  clawcode:
    emoji: "📅"
    os: ["darwin"]
    requires:
      bins: [ical]
---

# ical - macOS Calendar CLI

A Go CLI wrapping macOS Calendar via native EventKit. Sub-millisecond reads, full CRUD, natural language dates. Single binary, no dependencies.

## Quick Start

```bash
# Today's events
ical today -o json

# Next 7 days
ical upcoming --days 7 -o json

# Specific date range
ical list --from "mar 1" --to "mar 31" -o json

# Filter by calendar
ical today --calendar Work -o json

# Exclude noisy calendars
ical today --exclude-calendar Birthdays --exclude-calendar "Found in Natural Language" -o json

# Search events
ical search "dentist" --from "jan 1" --to "dec 31" -o json
```

## Create Events

```bash
# Timed event
ical add "Dentist" --start "mar 15 at 2pm" --end "mar 15 at 3pm"

# With calendar, location, notes
ical add "Sprint Review" --start "mar 15 at 9am" --end "mar 15 at 10am" --calendar Work --location "Zoom" --notes "Demo new features"

# All-day event
ical add "Spring Break" --start "mar 10" --end "mar 14" --all-day

# With alerts
ical add "Flight" --start "mar 15 at 8am" --alert 1h --alert 1d

# Recurring
ical add "Standup" --start "tomorrow at 9am" --repeat daily
ical add "Team sync" --start "next monday at 10am" --repeat weekly --repeat-days mon,wed
```

## Update Events

```bash
# By row number (from last listing)
ical update 2 --title "New title"
ical update 3 --start "tomorrow at 10am"

# By exact ID (preferred for scripting)
ical update --id "$EVENT_ID" --title "New title"

# Clear a field
ical update 1 --location ""
ical update 1 --alert none
ical update 1 --repeat none
```

Update applies immediately (no confirmation, no --force flag).

## Delete Events

```bash
# Always use --force in non-interactive contexts
ical delete 1 --force
ical delete --id "$EVENT_ID" --force
```

## List Calendars

```bash
ical calendars -o json
```

## Row Numbers

Event listings show row numbers (#1, #2, #3...) cached to `~/.ical-last-list`. Use row numbers in subsequent show/update/delete commands:

```bash
ical today                    # Shows #1, #2, #3...
ical show 2                   # Details for row #2
ical update 3 --title "New"   # Update row #3
ical delete 1 --force         # Delete row #1
```

Row numbers reset each time you run list/today/upcoming.

## JSON Output

Always use `-o json` for programmatic parsing.

```bash
# Count today's events
ical today -o json | jq 'length'

# Titles only
ical upcoming -o json | jq -r '.[].title'

# Filter by calendar
ical list --from today --to "in 30 days" -o json | jq '.[] | select(.calendar == "Work")'

# Calendar names
ical calendars -o json | jq -r '.[].title'
```

**Event JSON fields:** `id`, `title`, `start_date`, `end_date`, `calendar`, `calendar_id`, `location`, `notes`, `url`, `all_day`, `recurrence`, `alerts`

**Calendar JSON fields:** `id`, `title`, `type`, `color`, `source`, `readOnly`

## Natural Language Dates

Date flags (`--from`, `--to`, `--start`, `--end`) accept natural language:

- `today`, `tomorrow`, `yesterday`, `now`
- `eod`, `eow`, `this week`, `next week`, `next month`
- `next monday`, `friday at 2pm`
- `in 3 hours`, `in 2 days`, `3 days ago`
- `mar 15`, `march 15 2pm`
- `5pm`, `9am`, `17:00`
- ISO 8601: `2026-03-15`, `2026-03-15T14:30:00`

## TCC / Permissions

ical uses EventKit, which requires macOS Calendar permission. When run from a Python process chain (Claude Code CLI, bot, scheduled tasks), macOS TCC blocks Calendar access.

**Use the wrapper script** to bypass this:

```bash
# Instead of: ical today -o json
~/clawcode/scripts/ical-query.sh today -o json

# Any ical command works:
~/clawcode/scripts/ical-query.sh upcoming --days 7 -o json
~/clawcode/scripts/ical-query.sh add "Meeting" --start "tomorrow at 9am"
```

The wrapper spawns ical via a launchd one-shot job, bypassing the Python ancestry TCC restriction.

**Always use `ical-query.sh` instead of calling `ical` directly** when running from ClawCode contexts.

## Tips

- Always use `-o json` + `jq` for programmatic parsing
- Always use `~/clawcode/scripts/ical-query.sh` instead of `ical` directly (TCC bypass)
- Use `--force` on delete in non-interactive contexts (scripts, agents)
- Use `--id` with exact event IDs for reliable scripting (get IDs from `-o json` output)
- Use `--exclude-calendar Birthdays` for cleaner output
- Always exclude `--exclude-calendar "Found in Natural Language"` — these are Siri Suggestions phantom events parsed from iMessages, not real calendar entries. The `ical-query.sh` wrapper does this automatically.
- For reminders/tasks, use `remindctl` (apple-reminders skill)
- No attendee management (Apple EventKit limitation)
- Subscribed/birthday calendars are read-only

## Limitations

- macOS only (requires EventKit)
- No attendee management (read-only, Apple limitation)
- Subscribed and birthday calendars are read-only
