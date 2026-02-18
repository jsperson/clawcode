---
title: "feat: Proactive Heartbeat & Initiative Queue"
type: feat
date: 2026-02-17
builds_on: Phase 3 Autonomous Actions (2026-02-16)
brainstorm: docs/brainstorms/2026-02-17-proactive-heartbeat-brainstorm.md
---

# feat: Proactive Heartbeat & Initiative Queue

## Overview

Make ClawCode's heartbeat feel alive by adding cross-cycle memory (initiative queue), forcing functions that make silence harder, and inline state embedding so the heartbeat has context without depending on tool calls. No new architecture — we're adding a persistent file, a state tracker, and smarter prompts to the existing heartbeat loop.

## Problem Statement

The heartbeat runs reliably (~50+ cycles) but produces 90%+ silent `[heartbeat ok]` results. Zero proposals written, zero standing orders added, zero self-modifications to HEARTBEAT.md. The root cause is twofold:

1. **Amnesia** — each heartbeat cycle starts fresh with no memory of what previous cycles found, no queue of follow-ups, no sense of continuity.
2. **Silence is easy** — the prompt says "OK to find nothing" and `[heartbeat ok]` is the path of least resistance.

Phase 3 (Feb 16) added "bias toward action" language and broadened scan sources, but hasn't been battle-tested yet. Phase 4 builds on top of Phase 3 — not replacing it.

## Proposed Solution

Three additions to the existing heartbeat system:

1. **Initiative Queue** — a persistent markdown file in the Obsidian vault that gives the heartbeat memory and direction across cycles
2. **Heartbeat State Tracking** — a JSON file tracking cycle outcomes so the system can detect patterns (e.g., 5+ consecutive silent full-scans)
3. **Hybrid Prompt Design** — embed critical state (queue items, recent cycle outcomes, standing orders) directly in the heartbeat prompt instead of relying on tool calls

## Technical Approach

### File Ownership Model

The bot (Python) is responsible for **reading** state files and embedding their contents in prompts. Claude CLI is responsible for **writing** to them during heartbeat execution. This matches the existing pattern — the bot never writes vault files directly; all file I/O is delegated to Claude.

**One exception:** The bot writes `data/heartbeat-state.json` after each cycle to classify the outcome (silent/observation/action/proposal). This is a simple append-after-response operation that doesn't require Claude's judgment.

### Implementation Phases

#### Phase A: Initiative Queue (New File + Prompt Changes)

**New file:** `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Projects/ClawCode-Autonomy/initiative-queue.md`

```markdown
# Initiative Queue

Items for Computer to investigate, act on, or propose during heartbeat cycles.
Highest priority items get picked up first. Completed items move to Archive.

## Active

- [ ] **[high]** Seed 2-3 standing orders in HEARTBEAT.md (source: Phase 4 init, 2026-02-17)
- [ ] **[medium]** Check if RMMC dates (June 14-26) conflict with summer session (June 1 - July 25) and surface scheduling considerations (source: cross-domain, 2026-02-17)
- [ ] **[medium]** Review last 7 daily summaries for repeated manual tasks that could be automated (source: Phase 4 init, 2026-02-17)

## Archive

<!-- Completed items moved here with completion date -->
```

**Priority levels:** `high`, `medium`, `low`
**Format:** `- [ ] **[priority]** description (source, date added)`
**Cap:** 10-15 active items. Auto-archive after 30 days if untouched (via heartbeat prompt instruction — Claude checks dates and moves stale items to Archive during weekly reviews).

**Changes to `bot/main.py` `_build_heartbeat_prompt()`** (line 656):
- Read the initiative queue file and extract the Active section
- Embed top 5 items inline in the prompt
- For full-scan cycles, add instruction: "Pick the highest-priority initiative queue item and take action on it (within Tier 2 permissions). If the item needs Scott's approval, write a proposal."
- For all cycles (including lightweight), add instruction: "When you observe something worth following up on — a pattern, a scheduling conflict, a recurring task, an improvement opportunity — add it to the initiative queue at [path] with format `- [ ] **[priority]** description (source, date)`."
- Lightweight cycles see queue items for context but aren't required to act on them

**Changes to `bot/context.py` `build_context()`** (line 18):
- Add initiative queue summary (top 3 items) to conversation context so Claude can mention items in normal conversation ("By the way, I've been tracking X...")

#### Phase B: Heartbeat State Tracking (New File + Bot Logic)

**New file:** `data/heartbeat-state.json`

```json
{
  "cycles": [
    {
      "timestamp": "2026-02-17T14:30:00-06:00",
      "scan_type": "full",
      "outcome": "silent",
      "review_type": null
    }
  ],
  "consecutive_silent_full_scans": 0,
  "last_action_timestamp": null,
  "last_proposal_timestamp": null
}
```

**Outcome classification** (in `_process_message()`, line 860):
- `silent` — response contains `[heartbeat ok]`
- `observation` — response posted but no file writes detected (heuristic: response < 500 chars, no mention of "wrote", "created", "updated")
- `action` — response indicates a file write or task completion
- `proposal` — response mentions writing to proposals/

**Bot writes state after each cycle:**
- Append cycle entry to `cycles` array (keep last 20)
- Update `consecutive_silent_full_scans` counter (only count full-scan cycles, reset on any non-silent full-scan)
- Update `last_action_timestamp` / `last_proposal_timestamp` when applicable

**Embed in prompt:**
- Last 3 cycle summaries (one-line each)
- Consecutive silent count with flag if >= 5: "WARNING: {n} consecutive silent full-scans. This suggests checks are too passive. Look harder."

#### Phase C: Prompt Forcing Functions

**Changes to `_build_heartbeat_prompt()`:**

1. **Daily mini-review override** — Replace the Phase 3 "OK to find nothing on a quiet day" (line 695-697) with:
   ```
   "This is a daily mini-review. You MUST produce at least one observation, "
   "even if it's 'Nothing notable today because [specific reason].' "
   "Silence is not acceptable for review cycles."
   ```

2. **Weekly review accountability** — For weekly reviews, add:
   ```
   "If the previous weekly review produced zero proposals, explain why and try harder this time."
   ```

3. **Standing order seeding** — Pre-populate HEARTBEAT.md Standing Orders section with 2-3 starter orders so the section isn't blank. (One-time edit to `~/clawcode/HEARTBEAT.md` — live copy only. HEARTBEAT.md is a runtime file that self-modifies; the source template is just a starting point.)

**Standing orders to seed:**
```markdown
## Standing Orders
1. When scanning Apple Reminders, if any reminder is clearly completed (past due + done), mark it complete.
2. When reviewing daily summaries, flag any task that appears 3+ times without resolution — it may need a different approach or escalation.
3. When a weekly review produces zero proposals, the next full-scan cycle must attempt at least one proposal draft.
```

#### Phase D: Conversation Integration

**Changes to `bot/context.py` `build_context()`:**

Add a new section after "Memory Search" that reads the initiative queue and includes a summary:

```python
# Initiative queue summary for conversation context
queue_path = Path(config.paths.obsidian_vault) / "Projects/ClawCode-Autonomy/initiative-queue.md"
queue_content = _read_file(queue_path)
if queue_content:
    # Extract Active section, take top 3 items
    active_items = _extract_active_items(queue_content, limit=3)
    if active_items:
        parts.append(
            "## Initiative Queue (Top Items)\n\n"
            "These are items Computer is actively tracking. "
            "Mention relevant items in conversation when they connect to what Scott is discussing.\n\n"
            + "\n".join(active_items)
        )
```

The vault path is a constant (`OBSIDIAN_VAULT` in `bot/main.py`) — no config change needed for this.

### Files to Modify

**Source (`~/source/clawcode`) — code changes, committed to git:**

| File | Change | Lines |
|------|--------|-------|
| `bot/main.py` | `_build_heartbeat_prompt()` — read & embed queue + state | 656-723 |
| `bot/main.py` | `_process_message()` — classify outcome, write state | 860-887 |
| `bot/main.py` | Extract `OBSIDIAN_VAULT` constant from inline strings | lines 161, 274 |
| `bot/context.py` | `build_context()` — add queue summary section | 88-95 |

**Live (`~/clawcode`) — runtime config, NOT in git:**

| File | Change |
|------|--------|
| `HEARTBEAT.md` | Seed standing orders section (~line 241) |

**After code changes:** Deploy from source to live (`cp` specific changed `.py` files), then edit `~/clawcode/HEARTBEAT.md` directly for standing orders.

### Files to Create

**Live (`~/clawcode`) — runtime data:**

| File | Purpose |
|------|---------|
| `data/heartbeat-state.json` | Cycle outcome tracking (created automatically by bot on first cycle) |

**Obsidian vault — persistent queue:**

| File | Purpose |
|------|---------|
| `Projects/ClawCode-Autonomy/initiative-queue.md` | Initiative queue with seed items |

### Helper Functions to Add

In `bot/main.py`:

```python
# Extract existing inline vault path (bot/main.py:161, 274) to a module-level constant
OBSIDIAN_VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"

def _read_initiative_queue(limit: int = 5) -> list[str]:
    """Read top N active items from the initiative queue."""
    queue_path = OBSIDIAN_VAULT / "Projects/ClawCode-Autonomy/initiative-queue.md"
    # Parse Active section, return formatted items
    ...

def _read_heartbeat_state() -> dict:
    """Read heartbeat state, return empty defaults if missing."""
    state_path = Path(config.paths.data_dir) / "heartbeat-state.json"
    ...

def _write_heartbeat_state(state: dict) -> None:
    """Write updated heartbeat state after cycle completes."""
    ...

def _classify_heartbeat_outcome(response: str, is_silent: bool) -> str:
    """Classify heartbeat response as silent/observation/action/proposal."""
    ...
```

Note: `_read_initiative_queue()` is also used by `build_context()` in Phase D (with `limit=3`). Import it from `main.py` or move to a shared location.

## Acceptance Criteria

### Functional Requirements

- [x] Initiative queue file exists and has 2-3 seed items
- [x] Heartbeat prompt includes top 5 queue items on full-scan cycles
- [x] Heartbeat prompt includes last 3 cycle summaries
- [x] Bot writes `heartbeat-state.json` after every cycle
- [x] 5+ consecutive silent full-scans triggers warning in prompt
- [x] Daily mini-reviews require at least one observation (no silent exits)
- [x] Weekly reviews include accountability check for previous review
- [x] HEARTBEAT.md has 2-3 seeded standing orders
- [x] `build_context()` includes queue summary for conversation integration
- [x] Queue items follow format: `- [ ] **[priority]** description (source, date)`

### Quality Gates

- [x] Bot starts cleanly with missing state files (graceful defaults)
- [x] Queue parsing handles malformed markdown without crashing
- [x] State file doesn't grow unbounded (cap at 20 cycles)
- [x] No new dependencies added

## Success Metrics

- Initiative queue has items being added and acted on within 1 week
- At least one standing order added to HEARTBEAT.md by the system (not by Scott)
- At least one proposal written to proposals/ by the system
- Fewer than 50% of full-scan heartbeats return silent (currently ~90%)
- Scott says "that's useful" about something the system surfaced unprompted

## Dependencies & Risks

**Dependencies:**
- Phase 3 changes already deployed (confirmed)
- Obsidian vault accessible at known path (confirmed)
- `data/` directory exists and is writable (confirmed)

**Risks:**
- **Prompt length** — Embedding queue + state + standing orders adds ~500-800 chars. Current prompt is ~400 chars for full-scan. Should be fine — Claude's context window is massive.
- **Queue staleness** — Items could sit untouched. Mitigated by 30-day auto-archive and the "pick top item" forcing function.
- **Outcome classification heuristic** — Distinguishing "observation" from "action" by response content is imperfect. Acceptable for v1 — can refine based on real data.
- **Race condition** — If two heartbeat cycles run close together, state file could be overwritten. Mitigated by the 30-min interval — effectively impossible.

## What This Is NOT

- Not a new scheduler or process
- Not a rewrite of the heartbeat loop
- Not removing any existing guardrails
- Not giving the system new permissions beyond existing Tier 2
- Not replacing Phase 3 — building on top of it

## References

### Internal

- Brainstorm: `docs/brainstorms/2026-02-17-proactive-heartbeat-brainstorm.md`
- Phase 3 plan: `docs/plans/2026-02-16-feat-phase-3-autonomous-actions-plan.md`
- Heartbeat prompt builder: `bot/main.py:656`
- Heartbeat response handler: `bot/main.py:860`
- Context builder: `bot/context.py:18`
- HEARTBEAT.md: `~/clawcode/HEARTBEAT.md` (live, self-modifying)
- HEARTBEAT.md template: `~/source/clawcode/HEARTBEAT.md` (source)

### Obsidian

- Phase 4 brainstorm: `Projects/ClawCode-Autonomy/phase-4-brainstorm.md`
- Initiative queue (to create): `Projects/ClawCode-Autonomy/initiative-queue.md`
