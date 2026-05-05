# Life Agent Problem Solver — Brainstorm

**Date:** 2026-02-26
**Status:** Brainstorm complete

## What We're Building

An on-demand parallel research engine for life problems. User describes a problem — anything from parenting crises to home remodels to career decisions — and the agent researches it from multiple angles simultaneously, synthesizes findings, and optionally turns it into a living project plan.

This is compound-engineering's brainstorm→plan cycle adapted for life, not code.

## Why This Approach

- More concrete and well-scoped than the Phase 2 deep work cycle
- Immediate standalone value — doesn't depend on the overnight cycle
- Clear input→output flow with well-defined phases
- Parallel research pattern maps directly to existing Claude Code Task tool architecture
- Produces tangible artifacts (project docs with action plans)

## Key Decisions

### Invocation
- **Dedicated command** (`/life:solve` or `/life:problem`) for explicit invocation
- **Natural language recognition** — agent can also recognize when a conversation organically needs the full treatment
- Both paths lead to the same workflow

### Research Depth — Always Ask
- Agent does NOT guess the tier. Always asks: "This sounds like it needs the full treatment. Want me to go deep or keep it light?"
- Three tiers: quick answer, medium focused research, full parallel agents

### Research Sources — Full Context
- Web search (WebSearch + WebFetch) for external research
- Obsidian vault search for past notes, decisions, experiences
- QMD session/daily log search for relevant past conversations and context
- Agent should know what user has already dealt with before going external

### Output Location
- Write to `{notes_path}/Projects/` (vault root from config + Projects convention)
- No new config fields needed — uses existing `notes_path`
- Format: `{notes_path}/Projects/YYYY-MM-DD-topic.md` (or a subfolder for complex problems)

### Lens Selection — Fully Dynamic
- Orchestrator analyzes the problem and determines the right 3-4 research lenses each time
- No template library — trust the agent to figure out what angles matter
- Lenses adapt completely to the problem domain

### Living Plan Follow-up — Both Manual and Agent-Prompted
- Project doc is always available for manual checking and checkbox updates
- Evening review also surfaces open action items from active problem-solver projects
- Agent asks about specific items during review ("you were going to call the contractor — did that happen?")

### Knowledge Compounding — Deferred
- For v1, lessons flow through the normal evening review → observations → pattern → principle pipeline
- No special "resolve and capture" step yet
- Can add formal resolution workflow later if needed

### Synthesis Format — Structured Doc + TL;DR
- 3-5 bullet executive summary at the top for quick scanning
- Full structured sections below: situation summary, expert consensus (with sources), key people/resources, recommended actions (prioritized), things to watch for, divergent opinions
- Reference-friendly for coming back to later

## Architecture

### Phases

```
Phase 1: Problem Understanding (interactive)
  Quick dialogue — situation, constraints, what's been tried, what "solved" looks like
  Not a questionnaire — a conversation

Phase 2: Depth Check
  Always ask user: quick / medium / full parallel research

Phase 3: Parallel Research (if medium or full)
  Orchestrator picks 3-4 dynamically chosen lenses
  Each lens = one Task subagent running in parallel
  Each agent searches: web + vault + QMD sessions
  Returns structured findings

Phase 4: Synthesis
  Single agent distills all research into structured doc + TL;DR
  Writes to {notes_path}/Projects/

Phase 5: Living Plan (optional, on request)
  Turn recommendations into checklist project doc
  Checkboxes, follow-up prompts, timeline
  Evening review integration for active tracking
```

### Data Flow

```
User describes problem
  → Orchestrator: problem understanding dialogue
  → Orchestrator: ask depth preference
  → Orchestrator: determine research lenses (dynamic)
  → Task tool: spawn 3-4 parallel research agents
    Each agent: QMD search → vault search → web search → structured findings
  → Task tool: synthesis agent
    All findings → structured doc + TL;DR
  → Write to {notes_path}/Projects/YYYY-MM-DD-topic.md
  → (Optional) Convert to living plan with checkboxes
```

### Integration Points

- **Evening review:** Agent checks for active problem-solver projects, asks about open items
- **Overnight cycle:** Can reference active projects in daily plan flags (future — not wired in v1)
- **Observations pipeline:** Lessons flow naturally through evening review → observations.md

### Plugin Structure (new files)

```
commands/life/
  solve.md                    -- /life:solve orchestrator command
agents/
  problem-solver/
    researcher.md             -- Parallel research agent (one per lens)
    synthesizer.md            -- Distills findings into final doc
```

## Scope Calibration

The agent should match effort to problem size:

| Signal | Tier | What Happens |
|--------|------|--------------|
| Quick factual question | Quick | Just answer, no workflow |
| Focused problem, clear scope | Medium | 1-2 research agents, concise recommendations |
| Major life situation, multi-faceted | Full | 3-4 parallel agents, comprehensive synthesis, optional living plan |

Always confirmed with user — agent proposes tier, user decides.

## Open Questions

None — all resolved through dialogue.

## Example Flow

User: "My mom's health is declining and I need to figure out care options."

1. **Understanding:** Agent asks about current situation, location, budget, family dynamics, urgency
2. **Depth:** "This is a major life situation. Want me to do full parallel research?" → Yes
3. **Lenses chosen:**
   - Medical & Care Options — types of care (in-home, assisted living, memory care), what to look for, red flags
   - Financial & Legal — Medicare/Medicaid, long-term care insurance, power of attorney, estate planning
   - Family & Logistics — how to coordinate with siblings, caregiver burnout, local resources
   - Emotional & Relational — having the conversation, preserving dignity, grief/anticipatory grief
4. **Synthesis:** Structured doc with TL;DR, recommendations, people to talk to, timeline
5. **Living plan:** Checklist with next steps, follow-up tracking in evening reviews
