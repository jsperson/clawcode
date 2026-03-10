# ClawCode Capability Summary

Last updated: 2026-03-10

This file helps the scouting agent understand what ClawCode already does, so it can identify genuinely novel capabilities worth exploring.

## Core Platform

- **Runtime:** macOS (Mac Studio), bash, python3, Claude Code CLI
- **Bot:** Discord bot (discord.py) — receives messages, triggers Claude Code sessions
- **Scheduling:** launchd + schedule-runner.py — cron-based tasks invoke Claude CLI or bash scripts
- **Memory:** MEMORY.md (curated knowledge) + daily logs + QMD semantic search + FTS5 keyword search
- **Vault:** Obsidian (iCloud-synced) — personal notes, projects, journal, tasks

## Scheduled Tasks

- **life_overnight** (daily 02:00) — Life Agent generates daily plan from calendar, reminders, weather, Canvas, principles
- **daily_scout** (daily 04:00) — Capability scouting (this system)
- **daily_summary** (daily 06:30) — Summarize yesterday's conversation logs
- **daily_backup** (daily 01:00) — rsync to iCloud Drive
- **weekly_trends** (Monday 03:00) — Macro trends research across 6 domains, written to Obsidian
- **compound_plugin_check** (Tuesday 09:00) — Check Every's plugin repo for updates
- **weekly_experiment** (Wednesday 04:00) — Experiment with scouting finds in Docker

## Heartbeat System

- Runs every ~15-20 min (lightweight) and every ~2 hours (full-scan)
- 5 standing orders: reminder auto-completion, repeated task flagging, zero-proposal recovery, Canvas due-date scan, surfaced proposal follow-up
- Weekly review (Sunday 15:00): scans 7 sources, produces proposals
- Monthly deep review (1st weekday): skill audit, proposal cleanup, systemic friction scan

## Integrations

- **Gmail** — MCP server for read/send/search + bash script for attachments
- **Canvas LMS** — CLI tool for assignments, grades, discussions, announcements
- **Apple Reminders** — icalpal CLI wrapper for querying/completing tasks (6 lists: Home, Consulting, School, Family, Shopping, Side Projects)
- **Calendar** — icalpal CLI wrapper for events
- **QMD** — MCP server for semantic + keyword search across vault and memory
- **Browser** — Custom MCP server wrapping OpenClaw CLI for reliable browser automation (CDP relay + Chrome extension, persistent sessions)
- **Docker** — Docker Desktop installed, available for sandbox experimentation

## Skills

- apple-reminders, browser, calendar, canvas, daily-digest, gmail, icalpal, notes-inbound, scheduler, scott-vault

## Scripts

- backup.sh, daily-digest.sh, gmail-send-attachment.sh, gmail-mcp-start.sh, gmail-oauth-setup.sh, icalpal-query.sh, install.sh, memory-sync.sh, playwright-login.sh, plugin-deploy.sh, remindctl-query.sh, schedule-runner.py, schedule-sync.py

## Plugins

- **compound-engineering** (Every) — skills, agents, workflows for software development
- **life-agent** (Scott) — overnight planning, daily plans, principles-driven life management

## What We DON'T Do (Yet)

- No Apple Health data integration (scaffolded, waiting on Shortcut)
- No financial tracking or budgeting
- No smart home integration
- No RSS/feed aggregation
- No automated code deployment beyond plugin-deploy.sh
- Observation directories exist but are empty (life-agent/observations/*)
- No proactive file organization or cleanup
- No automated meeting prep or follow-up
