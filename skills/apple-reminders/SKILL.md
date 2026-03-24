---
name: apple-reminders
description: Manage Apple Reminders — create, list, complete, and query tasks.
  Use when user asks to "remind me", "add a reminder", "what are my tasks",
  "show reminders", "complete task", or discusses to-do items.
allowed-tools: Bash(remindctl-query:*)
metadata:
  clawcode:
    emoji: "⏰"
    os: ["darwin"]
    requires:
      bins: [remindctl]
---

# Apple Reminders CLI (remindctl)

Use `remindctl` to manage Apple Reminders directly from the terminal.

**Important:** Always use `remindctl-query.sh` (not `remindctl` directly) when running from Claude Code or SSH sessions. The wrapper bypasses macOS TCC restrictions via a launchd one-shot job.

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
remindctl-query.sh today

# Tomorrow
remindctl-query.sh tomorrow

# This week
remindctl-query.sh week

# Overdue items
remindctl-query.sh overdue

# Upcoming
remindctl-query.sh upcoming

# All reminders
remindctl-query.sh all

# Specific list
remindctl-query.sh list Home
```

### Create Reminders

```bash
# Quick add (defaults to Home list)
remindctl-query.sh add "Buy milk"

# With list and due date
remindctl-query.sh add --title "Call dentist" --list Home --due tomorrow

# With specific date
remindctl-query.sh add --title "Submit assignment" --list School --due 2026-02-15
```

### Complete Reminders

```bash
# Complete by UUID (always use UUIDs, not display numbers)
remindctl-query.sh complete 61A091EE-3FA8-4FEC-90C6-F6A4D1C6C23D
```

**Warning:** Display numbers like `[1]` in text output are global indexes across ALL reminders, not scoped to the current view. Always fetch `--json` first, extract the `id` field (UUID), and pass that to `complete`. Never use display numbers from filtered views like `upcoming` or `today`.

### Delete Reminders

```bash
remindctl-query.sh delete 4A83 --force
```

### Output Formats

```bash
# JSON for parsing
remindctl-query.sh today --json

# Plain TSV
remindctl-query.sh today --plain
```

## Date Formats

Accepted by `--due` and date filters:
- `today`, `tomorrow`, `yesterday`
- `YYYY-MM-DD` (e.g., `2026-02-15`)
- `YYYY-MM-DD HH:mm` (e.g., `2026-02-15 14:00`)
- ISO 8601 (`2026-02-15T14:00:00Z`)

## Calendar Events

For calendar event queries and creation, use `ical` (see the calendar skill).

## Tips

- Always use `--json` when you need to parse output programmatically
- Use `jq` for filtering and formatting JSON results
- When creating reminders, pick the most appropriate list from Scott's lists above
- Default to "Home" list for general personal reminders
- For morning briefings, combine `remindctl-query.sh today` + `remindctl-query.sh overdue` + `ical today -o json`
