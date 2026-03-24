---
title: Heartbeat icalpal TCC/FDA failure
category: runtime-errors
component: heartbeat, icalpal
date_solved: 2026-02-14
severity: medium
tags: [macos, tcc, fda, icalpal, heartbeat, launchd, calendar, reminders]
---

# Heartbeat icalpal TCC/FDA Failure

## Problem

Heartbeat lightweight checks for calendar events and Apple Reminders silently failed every cycle. The heartbeat reported `failed (icalpal issue)` and moved on (correctly following its "fail silently" guardrail), but never successfully checked calendar or reminders data.

## Symptoms

- Heartbeat logs show icalpal failures on every cycle
- No calendar or reminder data ever surfaces in heartbeat reports
- `icalpal` works fine when called directly from a terminal
- The wrapper script `icalpal-query.sh` also works fine from a terminal

## Root Cause

macOS TCC (Transparency, Consent, and Control) blocks calendar database access when `icalpal` is invoked from a Python process chain. The bot runs as `Python → Claude CLI → bash → icalpal`, and macOS denies Full Disk Access to processes with a Python ancestor.

The project already has a solution for this: `scripts/icalpal-query.sh` spawns icalpal through a launchd one-shot job (`launchd → bash → icalpal`), bypassing the Python ancestry requirement. The icalpal SKILL.md documents this requirement.

However, HEARTBEAT.md's lightweight checks said only:
```
- Check Apple Reminders for overdue or due-today items
- Check calendar for upcoming events in next 2 hours
```

No explicit command was specified. The heartbeat Claude session had to figure out *how* to query calendar/reminders. Even with the icalpal skill loaded in context, the session sometimes called `icalpal` directly instead of using the wrapper — hitting the TCC wall.

## Solution

Made the HEARTBEAT.md lightweight checks explicit about which command to run:

```markdown
- Check Apple Reminders for overdue or due-today items — run: `~/clawcode/scripts/icalpal-query.sh --compact uncompletedTasks -o json`
- Check calendar for upcoming events in next 2 hours — run: `~/clawcode/scripts/icalpal-query.sh --compact eventsToday -o json`
```

Changed in both `HEARTBEAT.md.template` (source) and deployed `HEARTBEAT.md` (live).

**Commit:** `6dd0ea9`

## Why This Worked

The heartbeat prompt is injected into a Claude session that reads HEARTBEAT.md and executes its checks. When the checks include explicit commands, Claude runs those commands verbatim rather than inferring the right tool. This removes the ambiguity that caused it to bypass the wrapper.

## Prevention

- **Be explicit in HEARTBEAT.md instructions.** When a check requires a specific tool or wrapper, include the exact command. Don't rely on Claude inferring the right approach from skill context.
- **Any new icalpal-dependent check** must use `~/clawcode/scripts/icalpal-query.sh`, never `icalpal` directly.
- **General principle:** Autonomous agent instructions (heartbeat, scheduled tasks) should be more explicit than interactive conversation instructions. In conversation, you can correct course; in autonomous loops, you can't.

## Related

- `scripts/ical-query.sh` — launchd one-shot wrapper for TCC bypass (replaced icalpal-query.sh)
- `skills/calendar-ical/SKILL.md` — ical CLI skill (documents wrapper requirement)
- The same TCC pattern applies to the `ical` CLI (EventKit-based) — Calendar permission is attributed to the parent process, so launchd wrapping is still required from Python contexts
