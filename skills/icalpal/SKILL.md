---
name: icalpal
description: Query macOS Calendar and Reminders via CLI. Use when user asks about
  "calendar", "events", "schedule", "meetings", "what's on my calendar",
  "what do I have today", "next meeting", or "free time".
allowed-tools: Bash(icalpal:*)
metadata:
  clawcode:
    emoji: "📅"
    os: ["darwin"]
    requires:
      bins: [icalpal]
---

# icalpal - macOS Calendar & Reminders CLI

Query macOS Calendar and Reminders databases directly. Read-only. Works with all calendar sources (iCloud, Google, Exchange, CalDAV, local).

## Quick Reference

### View Events

```bash
# Today's events
icalpal eventsToday

# Next 7 days
icalpal eventsToday+7

# Specific date
icalpal events --from 2026-01-30

# This week
icalpal events --from monday --to friday

# Currently happening
icalpal eventsNow

# Remaining today
icalpal eventsRemaining
```

### View Tasks (Reminders)

```bash
# All tasks
icalpal tasks

# Tasks with due dates
icalpal datedTasks

# Overdue tasks
icalpal tasksDueBefore --before today
```

### JSON Output (recommended for scripting)

```bash
icalpal eventsToday -o json
```

### Parse JSON with jq

```bash
# Today's events: time and title
icalpal eventsToday -o json | jq -r '.[] | "\(.sctime[11:16]) - \(.title)"'

# Filter by calendar
icalpal eventsToday -o json | jq '.[] | select(.calendar == "Work")'

# Event count
icalpal eventsToday -o json | jq 'length'

# Events with Zoom links
icalpal eventsToday -o json | jq '.[] | select(.notes | contains("zoom.us"))'
```

### Filtering

```bash
# Include specific calendars
icalpal eventsToday --calendars "Work,Personal"

# Exclude calendars
icalpal eventsToday --exclude-calendars "Birthdays,Holidays"
```

### Date Formats

- `today`, `tomorrow`, `yesterday`
- `monday`, `tuesday`, etc. (next occurrence)
- `YYYY-MM-DD`
- Relative: `+7 days`, `-1 week`

## Common Patterns

### Daily Digest

```bash
icalpal eventsToday -o json | jq -r '.[] | "- **\(.sctime[11:16])** \(.title)"'
```

### Next Meeting

```bash
icalpal eventsRemaining -o json | jq '.[0] | {time: .sctime, title: .title}'
```

## Tips

- Queries are fast (~100ms), safe to call frequently
- Read-only — cannot create or modify events
- Use `remindctl` (apple-reminders skill) for creating/managing reminders
- Always use `-o json` + `jq` for programmatic parsing
