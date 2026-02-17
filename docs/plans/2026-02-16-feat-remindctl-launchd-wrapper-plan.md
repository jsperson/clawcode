---
title: "feat: Add launchd wrapper for remindctl"
type: feat
date: 2026-02-16
---

# feat: Add launchd wrapper for remindctl

## Overview

Build `scripts/remindctl-query.sh` — a launchd one-shot wrapper for `remindctl` that bypasses macOS TCC restrictions, following the exact pattern of `scripts/icalpal-query.sh`. This enables the apple-reminders skill and automation scripts to work from Claude Code and SSH sessions.

## Problem Statement

macOS TCC denies Reminders access to processes with a Python ancestor in the process chain. When Claude Code (or the Discord bot) invokes `remindctl`, it fails with "Reminders access denied." The launchd one-shot pattern breaks the ancestry chain: `launchd -> bash -> remindctl` has no Python parent, so access is granted.

This is the same problem solved for icalpal two days ago (documented in `docs/solutions/runtime-errors/heartbeat-icalpal-tcc-failure.md`).

## Proposed Solution

Clone `scripts/icalpal-query.sh` and adapt for `remindctl`. No `--compact` flag needed initially — remindctl's JSON output is already minimal compared to icalpal's.

## Acceptance Criteria

- [x] `scripts/remindctl-query.sh` exists and follows icalpal-query.sh pattern
  - Dynamic plist with PID-based label (`com.clawcode.remindctl.$$`)
  - Temp files for stdout, stderr, exit code
  - `trap cleanup EXIT` for all exit paths
  - PATH includes `/opt/homebrew/bin`
  - Polling loop (0.25s intervals, max 10s)
  - Exit code preservation
- [x] Passes through all arguments to `remindctl` with proper quoting (`printf '%q'`)
- [x] Usage help when invoked with no arguments
- [x] `skills/apple-reminders/SKILL.md` updated:
  - `allowed-tools` changed from `Bash(remindctl:*)` to `Bash(remindctl-query:*)`
  - All examples updated to use `remindctl-query.sh` instead of `remindctl`
  - Note added explaining why the wrapper is required
- [x] All `remindctl` calls in `scripts/daily-digest.sh` replaced with wrapper
- [x] Grep confirms no remaining direct `remindctl` invocations in scripts (excluding the wrapper itself)
- [x] Tested from Claude Code session: `remindctl-query.sh today --json` returns data

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Compact flag | Skip for now | remindctl JSON is already minimal |
| Naming | `remindctl-query.sh` | Matches `icalpal-query.sh` convention |
| Timeout | 10s (40 polls x 0.25s) | Same as icalpal, remindctl is fast |
| Path to remindctl | Via PATH, not hardcoded | PATH in plist includes `/opt/homebrew/bin` |

## Files to Create/Modify

| File | Action |
|------|--------|
| `scripts/remindctl-query.sh` | **Create** — new wrapper script |
| `skills/apple-reminders/SKILL.md` | **Modify** — update allowed-tools and examples |
| `scripts/daily-digest.sh` | **Modify** — replace direct remindctl calls |

## References

- `scripts/icalpal-query.sh` — template to clone
- `docs/solutions/runtime-errors/heartbeat-icalpal-tcc-failure.md` — documented TCC solution
- `skills/apple-reminders/SKILL.md` — current skill definition
