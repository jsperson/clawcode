---
type: brainstorm
status: complete
created: 2026-02-24
supersedes: proposals/workflow-decision-persistence.md
---

# Decision Persistence

## What We're Building

A lightweight system for capturing decisions Scott makes in conversation so they persist across sessions and heartbeat cycles. Broader than the original ephemeral decision store proposal — this covers all decisions, not just calendar conflicts.

**Core problem:** Decisions made in chat evaporate at session end. The heartbeat re-flags resolved conflicts, re-surfaces settled questions, and generally acts like it has amnesia about choices Scott already made.

## Why This Approach

Single file, two decision types, natural lifecycle with human-in-the-loop promotion. Optimized for zero friction on capture and minimal noise on review.

Alternatives considered:
- **Event-specific only (original proposal):** Too narrow. Calendar conflicts are one case of a general problem.
- **Custom expiration per decision:** Adds friction at capture time. Two buckets (ephemeral/standing) cover 90% of cases without per-entry configuration.
- **Automatic promotion to permanent memory:** Risk of enshrining stale or bad decisions. Human checkpoint is worth the minor overhead.

## Key Decisions

### Two Buckets
- **Ephemeral** — tied to a specific event or deadline. Auto-expires when the date passes.
- **Standing** — ongoing until explicitly revoked or promoted. Carries creation timestamp.

### Capture: Fully Automatic
Computer captures decisions without asking. Both ephemeral and standing. Zero friction — if Computer misidentifies something, worst case is a stale entry that gets pruned.

### Storage: Single File
`memory/decisions.md` with entries in a flat list. Expected volume is 5-15 active entries at any time. No need to split files at this scale.

### Entry Format
```markdown
# Active Decisions

- 2026-02-24 | ephemeral | Skipping Startup Supper Club for Scholars Bowl | expires: 2026-02-24
- 2026-02-24 | standing | Using Docker approach for ClawCode sessions
```

Timestamp, type, description. Expiration date for ephemeral only. Standing decisions use creation date for the 30-day promotion clock.

### Lifecycle
1. **Capture** — Computer appends to `memory/decisions.md` when a decision is made in conversation
2. **Consult** — Heartbeat checks decisions.md before flagging conflicts or re-surfacing resolved items
3. **Prune** — Expired ephemeral entries removed during full-scan heartbeat cycles (no confirmation needed)
4. **Promote** — Standing decisions older than 30 days trigger a review checkpoint
5. **Review** — Surfaced during evening review, weekly cadence, only when promotions are pending

### Promotion Checkpoint (30 Days)
Standing decisions that survive 30 days aren't auto-promoted. Computer surfaces them during the weekly evening review with three options:
- **Promote** — moves to MEMORY.md or appropriate topic file
- **Extend** — resets the 30-day clock
- **Kill** — removed as stale

No pending promotions = no mention during review. Zero clutter.

## Open Questions

None — ready for planning.
