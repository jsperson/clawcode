---
name: apple-reminders
description: Manage Apple Reminders — create, list, complete, and query tasks.
  Use when user asks to "remind me", "add a reminder", "what are my tasks",
  "show reminders", "complete task", or discusses to-do items.
allowed-tools: Bash(remindctl:*)
metadata:
  clawcode:
    emoji: "⏰"
    os: ["darwin"]
    requires:
      bins: [remindctl]
---

# Apple Reminders CLI (remindctl)

Use `remindctl` to manage Apple Reminders directly from the terminal.

## Scott's Reminder Lists

- Home
- Consulting
- School
- Family
- Shopping
- Side Projects

Default to "Home" when no list is specified.

## Quick Reference

### View Reminders

```bash
# Today's reminders
remindctl today

# Tomorrow
remindctl tomorrow

# This week
remindctl week

# Overdue items
remindctl overdue

# Upcoming
remindctl upcoming

# All reminders
remindctl all

# Specific list
remindctl list Home
```

### Create Reminders

```bash
# Quick add (defaults to Home list)
remindctl add "Buy milk"

# With list and due date
remindctl add --title "Call dentist" --list Home --due tomorrow

# With specific date
remindctl add --title "Submit assignment" --list School --due 2026-02-15
```

### Complete Reminders

```bash
# Complete by ID (get IDs from list commands)
remindctl complete 1 2 3
```

### Delete Reminders

```bash
remindctl delete 4A83 --force
```

### Output Formats

```bash
# JSON for parsing
remindctl today --json

# Plain TSV
remindctl today --plain
```

## Date Formats

Accepted by `--due` and date filters:
- `today`, `tomorrow`, `yesterday`
- `YYYY-MM-DD` (e.g., `2026-02-15`)
- `YYYY-MM-DD HH:mm` (e.g., `2026-02-15 14:00`)
- ISO 8601 (`2026-02-15T14:00:00Z`)

## Calendar Events

For calendar event queries and creation, use `clawcal` (see the calendar skill).

## Tips

- Always use `--json` when you need to parse output programmatically
- Use `jq` for filtering and formatting JSON results
- When creating reminders, pick the most appropriate list from Scott's lists above
- Default to "Home" list for general personal reminders
- For morning briefings, combine `remindctl today` + `remindctl overdue` + `clawcal events`
