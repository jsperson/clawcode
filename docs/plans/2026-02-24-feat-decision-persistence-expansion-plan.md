---
title: "feat: Expand decision persistence to two-bucket lifecycle"
type: feat
status: active
date: 2026-02-24
origin: docs/brainstorms/2026-02-24-decision-persistence-brainstorm.md
---

# Expand Decision Persistence to Two-Bucket Lifecycle

Broaden `memory/decisions.md` from calendar-conflict-only ephemeral entries to a general-purpose decision store with two types (ephemeral and standing), automatic capture, and a 30-day promotion lifecycle with human review.

## Context

The original implementation (standing orders 16/17, lightweight check at line 47) handles one case: calendar scheduling conflicts with auto-expiring entries. The brainstorm (see brainstorm: `docs/brainstorms/2026-02-24-decision-persistence-brainstorm.md`) expands this to capture **all** decisions — project direction, preferences, deferred items — with a lifecycle that graduates durable decisions into permanent memory.

**What exists today:**
- `memory/decisions.md` — created, empty, single-format header
- HEARTBEAT.md standing order 16 — capture, but only "scheduling conflict or chooses between options"
- HEARTBEAT.md standing order 17 — prune expired entries
- HEARTBEAT.md line 47 — lightweight check reads decisions.md before flagging conflicts

**What changes:**
- File format gains two entry types (ephemeral + standing)
- Capture scope broadens to all decisions, not just scheduling
- Standing decisions get a 30-day promotion clock
- Evening review gains a weekly promotion checkpoint
- Lightweight check broadened to suppress any re-surfacing, not just calendar conflicts

## Acceptance Criteria

- [ ] `memory/decisions.md` header updated with two-type format and sections
- [ ] Standing order 16 rewritten: captures both ephemeral and standing decisions from any conversation, not just scheduling
- [ ] Standing order 17 rewritten: prunes expired ephemeral entries; flags standing entries older than 30 days for promotion review
- [ ] Lightweight check (line 47) broadened to suppress re-surfacing of any active decision, not just calendar conflicts
- [ ] New standing order added: during weekly evening review, surface standing decisions older than 30 days with Promote/Extend/Kill options
- [ ] Evening review integration documented (note in Life Agent or HEARTBEAT.md pointing to the promotion flow)

## Implementation

Six edits to three files. No code changes — all prompt-driven.

### 1. Update `memory/decisions.md`

Replace the current header and format with:

```markdown
# Active Decisions

Decisions captured from conversation. Heartbeat cycles check this file before re-flagging resolved items.

## Format

- Ephemeral: `- YYYY-MM-DD | ephemeral | description | expires: YYYY-MM-DD`
- Standing: `- YYYY-MM-DD | standing | description`

Ephemeral entries auto-expire. Standing entries persist until promoted to permanent memory, extended, or killed during evening review (30-day cycle).

---

<!-- Entries below this line. -->
```

### 2. Rewrite standing order 16 (decision capture)

**Current (line 282):**
> When Scott makes a decision in chat that resolves a scheduling conflict or chooses between options, append it to `memory/decisions.md`. Format: `- **YYYY-MM-DD** | decision text | expires: YYYY-MM-DD EOD`. Default expiration is end of the event day.

**New:**
> **Decision capture (any conversation)** — When Scott makes a decision in chat — scheduling choices, project direction, preferences, deferred items, or any choice between options — append it to `memory/decisions.md`. Use the appropriate type:
> - Ephemeral (tied to a specific event/deadline): `- YYYY-MM-DD | ephemeral | description | expires: YYYY-MM-DD`
> - Standing (ongoing until revoked): `- YYYY-MM-DD | standing | description`
>
> Default to ephemeral for scheduling/event decisions. Default to standing for project direction, preferences, and open-ended choices. Tier 2 — no confirmation needed.

### 3. Rewrite standing order 17 (pruning)

**Current (line 283):**
> Read `memory/decisions.md` and remove entries whose expiration date has passed.

**New:**
> **Decision maintenance (full-scan)** — Read `memory/decisions.md`. Remove ephemeral entries whose expiration date has passed. Do NOT remove standing entries — those follow the 30-day promotion lifecycle (see standing order 18). Tier 2 — no confirmation needed.

### 4. Add standing order 18 (promotion lifecycle)

New standing order:

> **Decision promotion review (weekly evening review)** — During the weekly evening review cycle, check `memory/decisions.md` for standing entries older than 30 days. For each, surface to Scott with three options: **Promote** (move to MEMORY.md or appropriate topic file and remove from decisions.md), **Extend** (reset the 30-day clock by updating the date), or **Kill** (remove as stale). If no standing entries are due for review, skip silently — no mention during the review.

### 5. Broaden lightweight check (line 47)

**Current:**
> Before flagging calendar conflicts or re-surfacing resolved items, read `memory/decisions.md` and suppress any alerts that match an active (non-expired) decision

**New:**
> Before flagging calendar conflicts, re-surfacing resolved items, or raising any issue that matches an active decision in `memory/decisions.md`, read the file and suppress the alert. Applies to both ephemeral and standing entries.

### 6. Document evening review integration

Add a comment or note in the Life Agent evening review skill (`skills/` or life-agent config) pointing to standing order 18 for the weekly promotion checkpoint. This ensures the evening review flow knows to check for pending promotions on its weekly cadence.

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-02-24-decision-persistence-brainstorm.md](docs/brainstorms/2026-02-24-decision-persistence-brainstorm.md) — key decisions: two buckets (ephemeral/standing), fully automatic capture, single file, 30-day promotion with human checkpoint during weekly evening review
- **Original proposal:** [proposals/workflow-decision-persistence.md](proposals/workflow-decision-persistence.md) — superseded by the brainstorm's expanded scope
- **Existing implementation:** HEARTBEAT.md standing orders 16-17, lightweight check line 47, `memory/decisions.md`
