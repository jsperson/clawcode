---
title: "feat: Capability Scouting & Self-Experimentation"
type: feat
status: completed
date: 2026-02-22
brainstorm: docs/brainstorms/2026-02-22-capability-scouting-brainstorm.md
---

# feat: Capability Scouting & Self-Experimentation

ClawCode proactively scouts for new AI agent capabilities from external sources, experiments with promising finds in a Docker sandbox, and reports results to Scott via Discord. The system evolves itself by discovering what's possible, not just executing what's asked.

## Acceptance Criteria

- [x] Daily scouting task runs at scheduled time, searches 2-3 sources, writes findings to scouting log
- [x] Scouting log accumulates daily with dated entries
- [x] Weekly experiment task reads the week's scouting log, picks the most promising find, experiments in Docker
- [x] Docker sandbox is isolated — experiments can't touch the host filesystem or ClawCode production
- [x] Successful experiments produce a proposal (existing proposal pipeline)
- [x] Failed experiments are logged with why they failed (learning, not just silence)
- [x] Discord messages summarize daily finds and weekly experiment results
- [x] Cost stays bounded: daily ~10 web searches, weekly experiment ~30 min Claude time
- [x] Scouting prompt includes ClawCode capability summary so Claude knows what's novel

## Architecture

### Two Scheduled Tasks

```
config/schedules.yaml:

  daily_scout:
    cron: "0 4 * * *"          # 04:00 daily (after overnight, before summary)
    prompt: <scouting prompt>
    enabled: true

  weekly_experiment:
    cron: "0 4 * * 3"          # 04:00 every Wednesday (mid-week, staggered from Monday trends)
    prompt: <experiment prompt>
    enabled: true
```

### Data Flow

```
Daily Scout (04:00)
  → Web search: Reddit, HN, web (2-3 sources, ~10 searches)
  → Filter: applicable to ClawCode? novel? achievable?
  → Write: data/scouting/YYYY-MM-DD.md
  → Discord: "Found N interesting things today" (brief)

Weekly Experiment (Wednesday 04:00)
  → Read: data/scouting/*.md from past 7 days
  → Pick: most promising find
  → Experiment: docker run in sandbox container
  → Evaluate: did it work? is it useful?
  → If success: write proposals/<type>-<name>.md
  → If failure: log why in data/scouting/experiments/YYYY-MM-DD-<slug>.md
  → Discord: detailed report of what was tried and result
```

### File Locations

| Path | Purpose |
|------|---------|
| `data/scouting/YYYY-MM-DD.md` | Daily scouting log entries |
| `data/scouting/experiments/YYYY-MM-DD-<slug>.md` | Experiment results (success or failure) |
| `proposals/<type>-<name>.md` | Successful experiments become proposals |
| `data/scouting/capabilities.md` | ClawCode capability summary (context for scout) |

## Implementation

### Phase 1: Scouting Infrastructure

#### 1.1 Create directory structure

```bash
mkdir -p ~/source/clawcode/data/scouting/experiments
```

#### 1.2 Write capability summary: `data/scouting/capabilities.md`

A living document the scouting prompt reads for self-awareness. Lists:
- What ClawCode currently does (scheduling, heartbeat, life agent, vault, Gmail, Canvas, reminders, calendar)
- What tools/MCP servers are available
- What the tech stack is (macOS, bash, python3, Claude Code CLI, Discord bot, Docker)
- What's been tried before (from proposals/ and experiments/)

This file gets updated manually or by the weekly experiment when new capabilities ship.

#### 1.3 Add `daily_scout` to `config/schedules.yaml`

**Prompt design (critical — this is what makes it work or produce noise):**

```yaml
daily_scout:
  cron: "0 4 * * *"
  prompt: >
    You are ClawCode's capability scout. Your job is to find new things
    ClawCode could do that it doesn't do yet.

    STEP 1: Read data/scouting/capabilities.md to understand what ClawCode
    already does.

    STEP 2: Search for recent AI agent capabilities, automations, and
    tools. Use ~10 web searches across these sources:
    - Reddit: r/ClaudeAI, r/claudeCode — what are people building?
    - Hacker News: "Claude Code" OR "AI agent" OR "MCP server" — new tools?
    - General web: "claude code automation 2026" — broader trends

    STEP 3: Filter ruthlessly. For each find, ask:
    - Is this applicable to ClawCode's stack? (macOS, bash, python, Claude CLI, Docker)
    - Is this genuinely novel? (not something we already do)
    - Could this be prototyped in a Docker sandbox in under 30 minutes?
    - Would Scott actually use this?
    If any answer is no, skip it.

    STEP 4: Write findings to data/scouting/YYYY-MM-DD.md using this format:

    ---
    date: YYYY-MM-DD
    sources_searched: [list]
    finds: N
    ---
    # Scout Report — YYYY-MM-DD

    ## Finds

    ### 1. <Title>
    **Source:** <URL>
    **What:** <1-2 sentences>
    **Why it matters:** <How ClawCode could use this>
    **Experiment idea:** <What to try in Docker>
    **Effort:** low | medium | high

    (repeat for each find, max 3-5 per day)

    ## Skipped
    - <Thing> — <why it was filtered out> (2-3 bullets max)

    STEP 5: Post a brief Discord summary:
    "Scout report: Found N things worth noting. Top find: <title>."
    If nothing passes the filter: "Scouted today. Nothing novel — all
    filtered out."

    CONSTRAINTS:
    - ~10 web searches maximum
    - Don't search for general AI news — search for BUILDABLE things
    - Don't recommend things that require paid APIs Scott doesn't have
    - Don't suggest life coaching features (Life Agent handles that)
    - Be honest when a day has nothing interesting
  enabled: true
```

#### 1.4 Add `weekly_experiment` to `config/schedules.yaml`

```yaml
weekly_experiment:
  cron: "0 4 * * 3"
  prompt: >
    You are ClawCode's experiment runner. Your job is to take the most
    promising find from this week's scouting and try it.

    STEP 1: Read all data/scouting/YYYY-MM-DD.md files from the past 7
    days. Pick the single most promising find based on:
    - Effort: prefer low/medium over high
    - Impact: prefer things Scott would use daily over novelties
    - Feasibility: prefer things that work with existing tools

    If no finds from the past week pass muster, report "Nothing worth
    experimenting with this week" and stop.

    STEP 2: Design the experiment. Write a brief plan:
    - What you're testing
    - What success looks like
    - What Docker image/setup you need
    - Time budget: 30 minutes max

    STEP 3: Run the experiment in Docker.
    - Use `docker run --rm` for ephemeral containers
    - Mount a temp directory for output: `-v /tmp/clawcode-experiment:/output`
    - DO NOT mount ClawCode directories, home directory, or .claude
    - Network access is fine (for installing packages, APIs, etc.)
    - If you need a base image: use `python:3.12-slim` or `node:22-slim`
    - Clean up containers when done

    STEP 4: Evaluate results.
    - Did it work?
    - Is it useful enough to propose for production?
    - What would need to change to wire it into ClawCode?

    STEP 5: Write results to data/scouting/experiments/YYYY-MM-DD-<slug>.md:

    ---
    date: YYYY-MM-DD
    source_find: <date and title of the scouting find>
    result: success | partial | failure
    ---
    # Experiment: <Title>

    ## What We Tried
    <Description>

    ## Setup
    <Docker commands, image, packages>

    ## Results
    <What happened, with output snippets>

    ## Assessment
    <Worth proposing? What would production integration look like?>

    ## Next Steps
    <Proposal created? Or why not?>

    STEP 6: If successful, create proposals/<type>-<name>.md following the
    existing proposal format (see proposals/ for examples). Set status: draft.

    STEP 7: Post to Discord with a detailed report:
    "Experiment report: Tried <title>. Result: <success/failure>.
    <2-3 sentence summary of what happened and what's next.>"

    CONSTRAINTS:
    - 30 minutes max experiment time
    - Docker only — never run untrusted code on the host
    - Don't install anything on the host system
    - Clean up all containers and temp files
    - If Docker isn't responding, report that and stop
  enabled: true
```

### Phase 2: Run Schedule Sync

After adding both entries to schedules.yaml:

```bash
python3 ~/clawcode/scripts/schedule-sync.py
launchctl list | grep clawcode.schedule
```

Verify both `daily_scout` and `weekly_experiment` appear in launchd.

### Phase 3: Bootstrap Capability Summary

Write initial `data/scouting/capabilities.md` summarizing ClawCode's current state:

- Scheduling system (launchd + schedule-runner)
- Heartbeat (5 standing orders, lightweight + full-scan cycles)
- Life Agent (overnight planning, daily plans, observations scaffold)
- Integrations (Gmail, Canvas, Apple Reminders, Calendar, QMD)
- Skills (apple-reminders, canvas, daily-digest, gmail, icalpal, notes-inbound, scheduler, scott-vault)
- Infrastructure (Discord bot, Claude Code CLI, Obsidian vault, Docker Desktop)
- MCP servers (Gmail, QMD, Playwright)
- Recent additions (plugin-deploy.sh, memory topic files)

This file is the scout's "what I already know" context.

## Design Decisions

### Why 04:00 for daily scout?
Runs after the overnight cycle (02:00) and before the daily summary (06:30). Results are available by the time Scott wakes up but don't interfere with other scheduled tasks.

### Why Wednesday for weekly experiment?
Staggered from Monday weekly trends (03:00 Monday) and Tuesday compound plugin check (09:00 Tuesday). Mid-week gives 3 days of scouting data to draw from while leaving the weekend buffer for the next cycle.

### Why `data/scouting/` not Obsidian vault?
Scouting logs are system operational data, not personal knowledge. They're ephemeral — most finds won't matter in a month. The vault is for durable knowledge. Proposals that graduate from experiments DO go to the standard proposals pipeline.

### Why Docker isolation?
ClawCode running arbitrary code from the internet on the host would be reckless. Docker gives full experimentation freedom (install anything, run anything) with zero host risk. The `--rm` flag ensures containers don't accumulate.

### Why not mount ClawCode directories?
The experiment should prove the concept in isolation. If it works, the proposal describes how to integrate it properly. Giving experiments access to production config/data creates risk for no benefit.

## What This Does NOT Do

- **Replace manual development.** Big features still get brainstormed and planned. This finds small, quick wins.
- **Self-deploy.** Experiments produce proposals. Scott decides what ships.
- **Life coaching.** The Life Agent handles Scott's habits and priorities. This is about ClawCode's capabilities.
- **Spend unlimited money.** Daily budget: ~10 web searches. Weekly: ~30 min Claude time + Docker.
- **Run on the host.** All experimentation happens in Docker containers.

## Verification

1. After adding schedules: `launchctl list | grep clawcode.schedule` shows both new tasks
2. First daily scout: check `data/scouting/YYYY-MM-DD.md` exists with formatted findings
3. First weekly experiment: check `data/scouting/experiments/YYYY-MM-DD-*.md` exists
4. Discord receives both daily and weekly notifications
5. No Docker containers left running after experiment: `docker ps` shows nothing from clawcode
6. After 2 weeks: evaluate signal-to-noise ratio. Are finds useful? Adjust sources or filters.

## Evolution Path

- **Week 1-2:** Run as-is, evaluate signal quality
- **Week 3+:** Tune sources based on what produced value (add GitHub trending? Drop a subreddit?)
- **Month 2+:** If experiments consistently produce good proposals, consider Option 3 from brainstorm (autonomous beta deployment)
- **Ongoing:** Update `capabilities.md` whenever new features ship so the scout stays current

## References

- Brainstorm: `docs/brainstorms/2026-02-22-capability-scouting-brainstorm.md`
- Schedule format: `config/schedules.yaml` (follow existing entries)
- Proposal format: `proposals/workflow-plugin-deploy-script.md`
- Schedule sync: `scripts/schedule-sync.py`
