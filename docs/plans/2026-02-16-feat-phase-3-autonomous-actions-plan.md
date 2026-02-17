---
title: "Phase 3: Make Self-Improvement Loop Produce Visible Output"
type: feat
date: 2026-02-16
brainstorm: docs/brainstorms/2026-02-16-phase-3-autonomous-actions-brainstorm.md
---

# Phase 3: Make Self-Improvement Loop Produce Visible Output

## Overview

Phase 2 built a self-improvement loop: weekly reviews, a proposal system, memory updates, standing orders. It's been live 3 days. The heartbeat fires, the weekly review ran on schedule, it found three real issues — then produced zero proposals, zero memory updates, and zero standing orders. The deployed HEARTBEAT.md is byte-for-byte identical to the template. Computer hasn't self-modified anything.

The quality bar told the system to be conservative. It was. Phase 3 fixes this with three changes:

1. **Flip the quality bar** — "silence is suspicious" replaces "noise erodes trust"
2. **Broaden the scan** — git history, skills, config, vault activity, HEARTBEAT.md self-review (not just daily logs)
3. **Add a daily mini-review** — short improvement scan during the 17:00-18:00 end-of-day window, giving 7x more opportunities to find and propose things

## Diagnosis: Why Phase 2 Produced Nothing

The weekly review on 2026-02-15 found three concrete issues:
- Plugin deployment is the highest-friction workflow
- Bot error responses are opaque (no stack traces in logs)
- Heartbeat digest check produces false positives

It then wrote: *"Proposals created: none (system too new for recurring patterns; quality bar applied)"*

Four lines in HEARTBEAT.md.template caused this:
- `"Only propose something if you'd bet it saves Scott time or prevents a real problem"` (line 86)
- `"Proposals are how you build trust for Phase 3 autonomy — noisy or low-value proposals erode trust"` (line 88)
- `"Apply the quality bar: only surface patterns that are genuine, recurring, and actionable"` (line 131)
- `"Quality over quantity — fewer, better proposals build trust; noise erodes it"` (line 189)

Each issue *was* a real problem. The cumulative weight of "be careful" language made doing nothing the optimal strategy.

Second problem: the scan only looks at daily logs via `clawcode memory search`. It doesn't check git history, existing skills, config, vault structure, or its own HEARTBEAT.md. Narrow input = narrow output.

## Changes Overview

| # | File | Action | Description |
|---|------|--------|-------------|
| 1 | `HEARTBEAT.md.template` | Modify | Rewrite quality bar, broaden scan targets, rewrite guardrails, add daily mini-review, add vault activity scan, enumerate Tier 2 actions |
| 2 | `bot/main.py` | Modify | Add daily mini-review detection to `_build_heartbeat_prompt()` |
| 3 | Deployed `HEARTBEAT.md` | Overwrite | Re-seed from updated template (deployed copy is identical — nothing to preserve) |

3 files. Content-heavy, code-light.

## Detailed Implementation

### 1. `HEARTBEAT.md.template`

#### 1a. Replace Quality Bar (lines 83-88)

**Current:**
```markdown
### Quality Bar

- One sharp, specific observation is worth more than five vague ones
- Only propose something if you'd bet it saves Scott time or prevents a real problem
- If a weekly review finds nothing worth proposing, that's a good outcome — but still post the review summary
- Proposals are how you build trust for Phase 3 autonomy — noisy or low-value proposals erode trust
```

**Replace with:**
```markdown
### Bias Toward Action

- **If you notice something, propose it.** A rejected proposal costs nothing. A missed improvement costs time.
- **Proposals are cheap, silence is expensive.** Scott would rather review and reject three proposals than wonder if the system is doing anything.
- **Specificity matters.** "The plugin deployment workflow is painful" is weak. "Plugin deployment failed 3 times this week because version strings don't auto-increment — here's a fix" is strong. Be specific, but don't let imperfect specificity stop you from proposing.
- **A review that produces nothing is a red flag.** If you scanned all sources and found nothing to propose, update, or improve, you probably didn't look hard enough. Expand your search. Something can always be better.
- **Act on what you can, propose what you can't.** MEMORY.md appends, HEARTBEAT.md standing orders, and vault reference notes don't need proposals — just do them. Proposals are for things requiring Scott's approval (skill changes, identity edits, structural changes).
```

#### 1b. Enumerate Tier 2 Actions (replace lines 10-11)

**Current:**
```markdown
### Tier 2 — Decide & Act (Full Scan)
Take action within guardrails. These run on full-scan cycles only (default: every 4th cycle / ~2 hours).
```

**Replace with:**
```markdown
### Tier 2 — Decide & Act (Full Scan)
Take action within guardrails. These run on full-scan cycles only (default: every 4th cycle / ~2 hours).

**Approved autonomous actions (no confirmation needed):**
- Append entries to MEMORY.md (never delete existing entries)
- Add, update, or remove standing orders in this document
- Write reference notes to the Obsidian vault (Ideas/ or Projects/)
- Update HEARTBEAT.md check descriptions for accuracy
- Complete Apple Reminders that are clearly done based on conversation context

**Requires confirmation (post to Discord and wait):**
- Any action that modifies skill definitions, identity files, or config schema
- Any action not on the approved list above
- Anything irreversible
```

#### 1c. Broaden Weekly Review Scan (replace lines 122-131)

**Current pattern scan step:**
```markdown
1. **Pattern scan** — search past 7 daily logs using explicit CLI invocations:
   ```
   clawcode memory search "<topic>" --source daily --limit 10
   ```
   Look for:
   - Questions asked repeatedly → MEMORY.md candidate
   - Workflows that took multiple attempts → skill/workflow proposal candidate
   - Information looked up repeatedly → reference doc or MEMORY.md candidate
   - Heartbeat errors or retries → process improvement candidate
   - Apply the quality bar: only surface patterns that are genuine, recurring, and actionable
```

**Replace with:**
```markdown
1. **Pattern scan** — cast a wide net across multiple sources. Don't stop at daily logs.

   **Daily logs** (primary source) — search past 7 daily logs:
   ```
   clawcode memory search "<topic>" --source daily --limit 10
   ```
   Look for:
   - Questions asked repeatedly → MEMORY.md entry or reference doc
   - Workflows that took multiple attempts → skill or workflow proposal
   - Information looked up repeatedly → MEMORY.md entry
   - Errors, retries, or workarounds → process improvement proposal
   - Things Scott said he'd do later or follow up on → standing order to track it

   **Git history** — check what changed this week:
   ```
   git -C ~/source/clawcode log --oneline --since="7 days ago"
   ```
   Look for: files touched repeatedly, recurring fixes, patterns in what's being modified.

   **Existing skills** — read 2-3 `skills/*/SKILL.md` files per review (rotate through all skills over time). Are instructions still accurate? Do triggers match actual usage? Any gaps?

   **HEARTBEAT.md self-review** — re-read your own standing orders and checks. Are any stale? Missing? Should findings from this review become a new standing order?

   **Config** — quick scan of `config/config.yaml`. Any settings that could be tuned? Features enabled but unused? Gaps?

   **Vault activity** — check recently modified files in the Obsidian vault:
   ```
   find ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/scott/ -name "*.md" -mtime -7 -not -path "*/Archive/*" -not -path "*/.trash/*" | head -20
   ```
   "Things done indicates things that needed doing." If Scott manually filed, created, or updated notes — are any of those tasks automatable? Could a skill or standing order handle them?

   **Minimum output:** Every weekly review MUST produce at least one of: a MEMORY.md update, a new/updated standing order, or a proposal. If you genuinely can't find anything after scanning all sources, explain what you checked and why — but this should be rare.
```

#### 1d. Add Daily Mini-Review to Full Scan Checks (after line 39)

Add to the "Full Scan Checks" section:

```markdown
- Daily mini-review (if running in 17:00-18:00 window, any day):
  - Quick improvement scan — 2-3 minutes max
  - Check today's git activity: `git -C ~/source/clawcode log --oneline --since="today"`
  - Scan today's daily log for unresolved items or patterns
  - Re-read HEARTBEAT.md standing orders — anything to update?
  - Check Obsidian vault for files modified today: `find ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/scott/ -name "*.md" -mtime -1 -not -path "*/Archive/*" -not -path "*/.trash/*" | head -10`
  - May produce: proposals, MEMORY.md updates, standing order changes
  - Same minimum output rule does NOT apply to daily mini-reviews — it's OK to find nothing on a quiet day. But if there was activity, look for improvements.
```

#### 1e. Rewrite Self-Improvement Guardrails (replace lines 185-191)

**Current:**
```markdown
### Self-Improvement Guardrails

- **Propose, don't act** on identity files, skill definitions, or structural changes
- **MEMORY.md appends are safe** — never delete existing entries
- **Quality over quantity** — fewer, better proposals build trust; noise erodes it
- **Cite evidence** — proposals without specific log references are weak proposals
- **Time budgets:** weekly review up to 10 min, monthly review up to 15 min, regular heartbeat 2-3 min
```

**Replace with:**
```markdown
### Self-Improvement Guardrails

- **Propose, don't act** on identity files (SOUL.md, STYLE.md), skill definitions (SKILL.md files), or structural changes (new directories, config schema changes)
- **Act directly** on: MEMORY.md appends, HEARTBEAT.md standing orders, vault reference notes. These are within your Tier 2 permissions and don't need proposals.
- **MEMORY.md appends are safe** — never delete existing entries, but add freely. If you learned something durable, write it down. Don't overthink whether it's "important enough."
- **Cite evidence** — proposals are stronger with specific references, but don't let "I can't find the exact log line" stop you from proposing something you know is true from session context.
- **Time budgets:** weekly review up to 10 min, monthly review up to 15 min, daily mini-review 2-3 min, regular heartbeat 2-3 min
```

#### 1f. Update Context Enhancement (replace lines 179-183)

**Current:**
```markdown
### Context Enhancement (any full scan)

- If recent work produced genuinely reusable reference knowledge, write a vault note following scott-vault routing (Ideas/ for research, Projects/ for active work)
- Add pointer in MEMORY.md for future sessions
- High bar: only for durable knowledge, not ephemeral conversation artifacts
```

**Replace with:**
```markdown
### Context Enhancement (any full scan)

- If recent work produced reusable knowledge, write a vault note following scott-vault routing
- Add pointer in MEMORY.md for future sessions
- Bias toward writing it down — a note that turns out unnecessary is easy to delete, but knowledge lost because "it didn't seem important enough" is gone forever
```

### 2. `bot/main.py` — Daily Mini-Review Detection

**Modify `_build_heartbeat_prompt()` (line ~668)**

The function already detects weekly (Sunday 15:00-17:00) and monthly (1st weekday 14:00-16:00) review windows. Add daily mini-review detection:

```python
# After the weekly review check, add:
# Daily mini-review: 17:00-18:00 any day (piggyback on end-of-day window)
elif is_full_scan and 17 <= now.hour < 18:
    review_type = "daily-mini"
    time_budget = "2-3 minutes"
```

This goes inside the existing `if is_full_scan:` block, after the monthly and weekly checks. The end-of-day summary already fires in this window — the mini-review adds an improvement scan to that cycle.

Update the review type prompt injection to handle the new type:

```python
if review_type:
    proposals_dir = Path(config.paths.project_dir) / "proposals"
    parts.append(f"Review type: {review_type}")
    if review_type == "daily-mini":
        parts.append(
            "This is a daily mini-review. Run the daily mini-review checks "
            "from HEARTBEAT.md. Quick scan only — 2-3 minutes max. "
            "OK to find nothing on a quiet day, but if there was activity today, "
            "look for improvements."
        )
    else:
        parts.append(
            f"This is a {review_type} review cycle. Follow the "
            f"Self-Improvement Protocol in HEARTBEAT.md for the "
            f"{review_type} review checklist."
        )
    parts.append(f"Proposals directory: {proposals_dir}")
```

### 3. Re-seed Deployed HEARTBEAT.md

The deployed copy at `~/clawcode/HEARTBEAT.md` is identical to the template. Computer has not self-modified it. Safe to overwrite after updating the template:

```bash
cp ~/source/clawcode/HEARTBEAT.md.template ~/clawcode/HEARTBEAT.md
```

## What's NOT in Phase 3

- **Inbox processing** — deferred to Phase 3b. Get proposals working first.
- **Inbox routing rules / inbox-rules.md** — deferred with inbox processing.
- **Proposal approval commands** — stays conversational. No `/approve` or `/reject`.
- **Auto-approve escalation** — no `auto: true` rules yet.
- **Expanded autonomous action list** — keep current Tier 2 permissions, just enumerate them explicitly.

## Acceptance Criteria

- [ ] Weekly review produces at least one visible output (proposal, memory update, or standing order)
- [ ] Weekly review scans all sources: daily logs, git history, skills, config, vault activity, HEARTBEAT.md
- [x] Daily mini-review fires in 17:00-18:00 window during full-scan cycles
- [x] Daily mini-review can produce proposals and memory updates
- [x] Tier 2 autonomous actions are explicitly enumerated in HEARTBEAT.md
- [x] Self-improvement guardrails clearly distinguish "act directly" vs "propose"
- [x] Deployed HEARTBEAT.md reflects all template changes
- [ ] No regression in normal heartbeat operation (calendar, reminders, Canvas checks)

## Verification

1. **Trigger a review manually:** Temporarily set the daily mini-review window to the current hour in `_build_heartbeat_prompt()`. Restart bot. Wait for a full-scan heartbeat. Verify it produces output (check Discord and the vault review log).
2. **Check scan breadth:** Read the review summary in `Projects/ClawCode-Autonomy/reviews/`. Verify it mentions git history, skills, and vault activity — not just daily logs.
3. **Regression check:** Verify lightweight heartbeats still fire silently with `[heartbeat ok]` when nothing is actionable. Full scans should still report calendar and reminders normally.
4. **Read deployed HEARTBEAT.md:** Confirm quality bar says "Bias Toward Action", Tier 2 has explicit action list, guardrails distinguish "act directly" vs "propose".

## Implementation Order

1. `HEARTBEAT.md.template` — all content changes (quality bar, Tier 2 enumeration, scan targets, daily mini-review, guardrails, context enhancement)
2. `bot/main.py` — daily mini-review detection in `_build_heartbeat_prompt()`
3. Deploy: copy template → `HEARTBEAT.md`, copy `bot/main.py` → deployed
4. Restart bot
5. Verify with manual trigger
6. Wait for next natural review window to confirm end-to-end
7. Commit and push

## Rollback

If the system generates too much noise:
1. Restore previous `HEARTBEAT.md.template` from git
2. Re-seed deployed `HEARTBEAT.md`
3. Revert `bot/main.py` daily-mini detection
4. Restart bot

All changes are in two files plus a template copy. Fully reversible in under 5 minutes.
