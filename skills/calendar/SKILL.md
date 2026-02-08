---
name: calendar
description: Query and create macOS Calendar events via CLI. Use when user asks about
  "calendar", "events", "schedule", "meetings", "what's on my calendar",
  "what do I have today", "next meeting", "free time", or "create an event".
allowed-tools: Bash(clawcal:*)
metadata:
  clawcode:
    emoji: "📅"
    os: ["darwin"]
    requires:
      bins: [clawcal]
---

# clawcal - macOS Calendar CLI

Read and write macOS Calendar events using EventKit. Works with all calendar sources (iCloud, Google, Exchange, CalDAV, local). Always outputs JSON.

## Read Events

```bash
# Today's events
clawcal events

# Next 7 days
clawcal events --days 7

# Specific date range
clawcal events --from 2026-06-01 --to 2026-06-30

# Filter by calendar
clawcal events --calendars "Work,School"

# Exclude calendars
clawcal events --exclude "Birthdays,Found in Natural Language"

# Combine options
clawcal events --days 7 --exclude "Birthdays"
```

### Event JSON Format

```json
[
  {"date":"2026-06-15","start":"09:00","end":"10:00","title":"Meeting","calendar":"Work","location":"","all_day":false}
]
```

### Parse with jq

```bash
# Time and title
clawcal events | jq -r '.[] | "\(.start) \(.title)"'

# Filter by calendar
clawcal events --days 7 | jq '.[] | select(.calendar == "Work")'

# Count events
clawcal events | jq 'length'

# Events with location
clawcal events --days 7 | jq '.[] | select(.location != "")'
```

## Create Events

```bash
# Timed event
clawcal add "Dentist" --date 2026-03-15 --start 14:00 --end 15:00

# With calendar, location, notes
clawcal add "Sprint Review" --date 2026-03-15 --start 09:00 --end 10:00 --calendar Work --location "Zoom" --notes "Demo new features"

# All-day event
clawcal add "Spring Break" --date 2026-03-10 --end-date 2026-03-14 --all-day

# Defaults: 1 hour duration, default calendar
clawcal add "Quick call" --date tomorrow --start 15:00
```

## List Calendars

```bash
clawcal calendars
```

## Date Formats

- `today`, `tomorrow`, `yesterday`
- `monday` through `sunday` (next occurrence)
- `YYYY-MM-DD` (e.g. `2026-06-15`)
- `+Ndays` / `-Ndays` (e.g. `+7days`, `-1days`)

## Tips

- Use `--exclude "Birthdays,Found in Natural Language"` for cleaner output
- For reminders/tasks, use `remindctl` (apple-reminders skill)
- All output is JSON — pipe through `jq` for formatting
- `--end` defaults to 1 hour after `--start` if omitted
