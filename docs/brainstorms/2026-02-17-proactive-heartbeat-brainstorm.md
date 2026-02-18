# Brainstorm: Proactive Heartbeat & Initiative Queue

**Date:** 2026-02-17
**Status:** Draft
**Builds on:** Phase 3 Autonomous Actions (2026-02-16)

## What We're Building

Make ClawCode's heartbeat feel alive — not just a watchdog that checks things and says "all clear," but a system that notices patterns, takes autonomous action within guardrails, connects dots across domains (school + family + work), and surfaces things Scott hasn't thought of. The goal: ClawCode should be doing useful things even when Scott isn't talking to it.

## Why This Approach

Phase 3 (Feb 16) correctly diagnosed the problem — silence was too safe, the instructions made doing nothing the path of least resistance. The rewrite added "bias toward action" language and broadened the scan sources from 1 to 7. But Phase 3 hasn't been battle-tested in a weekly review yet (next: Feb 22), and the daily mini-reviews still allow "nothing found."

The deeper issue: each heartbeat cycle is **amnesic**. Claude has no memory of what previous heartbeats found, no queue of things to follow up on, and no sense of continuity between cycles. Even with perfect prompts, a system that forgets everything every 30 minutes can't build momentum.

**We're NOT changing the architecture.** No new schedulers, no new processes. We're adding:
1. An initiative queue (persistent file) that gives the heartbeat memory and direction
2. Forcing functions that make silence harder and action more natural
3. Hybrid prompt design that embeds critical state inline

## Key Decisions

### Initiative Queue
- **Location:** Obsidian vault at `Projects/ClawCode-Autonomy/initiative-queue.md`
- **Format:** Markdown checklist. Each item: `- [ ] **[priority]** description (source, date added)`. Completed items get checked off and moved to an Archive section at the bottom.
- **Fed by:** Heartbeat observations, daily summary patterns, weekly review findings
- **Consumed by:** Next heartbeat cycle picks highest-priority item and acts on it (within Tier 2 permissions)
- **Also visible in:** Regular conversations — Claude reads the queue and can say "by the way, I've been tracking X"
- **Lifecycle:** Items added → acted on → resolved or escalated to Scott

### Forcing Functions
- **Heartbeat state file:** `data/heartbeat-state.json` — tracks what each cycle produced (silent/observation/action/proposal) and last 10 cycle results. Flag 5+ consecutive silent full-scan cycles as a problem.
- **Daily mini-review minimum:** Change from "OK to find nothing" to "must produce at least one observation, even if it's 'nothing notable today because X'"
- **Weekly review accountability:** If the previous weekly review produced zero proposals, the next one must explain why and try harder
- **Standing order seeding:** Pre-populate 2-3 starter standing orders so the section isn't blank. The system is more likely to add to a list that already has items than to start from zero.

### Prompt Design (Hybrid)
- **Embed inline:** Standing orders, current initiative queue items (top 5), heartbeat state (last 3 cycles summary), today's daily summary if available
- **Read from disk:** Full HEARTBEAT.md protocol (for review cycles), full initiative queue (for weekly reviews), proposal directory contents
- **Rationale:** Critical context shouldn't depend on a tool call succeeding. Full protocol is too large to embed every cycle.

### Cross-Domain Intelligence
- Not a separate feature to build — it's an emergent property of the initiative queue. When the heartbeat scans calendar and finds RMMC dates overlapping with summer session, that becomes a queue item. When daily summaries show repeated manual tasks, that becomes a queue item. The weekly review connects them. No special code needed — just the right prompt instructions.

### Autonomous Actions (Within Existing Tier 2)
No new permissions needed. The heartbeat already has Tier 2 approval for:
- Append to MEMORY.md
- Add/update standing orders in HEARTBEAT.md
- Write vault notes (Ideas/ or Projects/)
- Update HEARTBEAT.md check descriptions
- Complete clearly-done Apple Reminders

The initiative queue adds a forcing function: "pick the top item and do something about it." The action might be writing a proposal (if it needs Scott's approval) or just doing it (if it's within Tier 2).

### Implementation Timing
- Implement in parallel with Phase 3 — these changes complement it, not replace it. Sunday's weekly review (Feb 22) will be the first test of both together.

### Conversation Integration
- Yes — Claude should mention initiative queue items during normal conversations when relevant. ("By the way, I've been tracking X...") This is core to feeling alive, not just a heartbeat feature.

## Open Questions

1. **Initiative queue size management** — How many items before it gets noisy? Cap at 10-15 active items? Auto-archive after 30 days?
2. **Feedback mechanism** — How does the system know if Scott found a proposal useful? Discord reactions? Explicit approve/reject? Or just track whether proposals get discussed?

## What This Is NOT

- Not a new scheduler or process
- Not a rewrite of the heartbeat loop
- Not removing any existing guardrails
- Not giving the system new permissions it doesn't already have
- Not replacing Phase 3 — building on top of it

## Success Criteria

- Initiative queue has items being added and acted on within 1 week
- At least one standing order added to HEARTBEAT.md by the system (not by Scott)
- At least one proposal written to proposals/ by the system
- Fewer than 50% of full-scan heartbeats return silent (currently ~90% silent)
- Scott says "that's useful" about something the system surfaced unprompted
