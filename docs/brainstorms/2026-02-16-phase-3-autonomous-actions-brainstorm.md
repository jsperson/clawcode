---
topic: "Phase 3: Autonomous Actions"
date: 2026-02-16
status: complete
---

# Phase 3: Autonomous Actions — Brainstorm

## What We're Building

Make the self-improvement loop produce visible output. Phase 2 built the machinery (weekly reviews, proposal system, memory updates). It runs, it scans, it finds real issues — then it does nothing because the quality bar says "be careful." Phase 3 fixes this.

**Success looks like:** Scott sees proposals in Discord that prove the system is thinking. Things like "plugin deployment failed 3 times this week — here's a fix proposal" or "you manually filed 4 lawn care notes this month — want me to create a routing rule?"

## Why This Approach

The system already works mechanically. The heartbeat fires, reviews run on schedule, the proposal directory exists. The problem is entirely in the instructions — HEARTBEAT.md.template tells Computer to be so cautious that doing nothing is the optimal strategy. Fix the instructions, fix the output.

Two levers:
1. **Lower the bar** — change the language from "noise erodes trust" to "silence erodes trust"
2. **Broaden the scan** — the weekly review only searches daily logs. It should also check git history, existing skills, config, vault structure, and recent Obsidian activity

Add a third lever for faster feedback:
3. **Daily mini-review** — don't wait until Sunday to find improvement opportunities. A short daily scan during one full-scan cycle gives 7x more chances to propose things.

## Key Decisions

### 1. Focus on proposals, not inbox processing
Inbox processing is a new capability. Proposals are an existing capability that isn't working. Fix what's broken before adding new things. Inbox deferred to Phase 3b or Phase 4.

### 2. "Things done indicates things that needed doing"
Scott's recent Obsidian activity is a signal source. If he manually filed notes, created projects, or wrote docs — those are automation candidates. The review should scan recent vault modifications (via `find` or `ls -lt`) to spot patterns.

### 3. Daily mini-review, not just weekly
A short (2-3 min) daily improvement scan during one full-scan cycle. Lighter than the weekly review — just a quick "anything obvious to improve today?" Not a replacement for the weekly deep dive, but a supplement that creates more surface area for proposals.

### 4. Approval stays conversational
Computer posts proposal to Discord. Scott replies "approved", "nah", "good idea but change X". No emoji reactions, no commands, no structured approval flows. Keep it natural.

### 5. Minimum output requirement
Every weekly review MUST produce at least one proposal, memory update, or standing order. "Nothing found" after scanning all sources is a failure of the scan, not a success of the system.

### 6. Quality bar flipped, not removed
The bar isn't eliminated — proposals still need specificity and evidence. But the framing changes from "don't propose unless you're sure" to "propose anything you notice, be specific about why." A rejected proposal is fine. Zero proposals is not.

## Scan Sources (Expanded)

| Source | What to look for | Cadence |
|--------|-----------------|---------|
| Daily logs (`memory search`) | Repeated questions, workflow friction, lookup patterns | Weekly + daily mini |
| Git history (`git log`) | Recurring fixes, files changed repeatedly, patterns in commits | Weekly |
| Skills (`skills/*/SKILL.md`) | Accuracy, trigger coverage, gaps, stale instructions | Weekly (rotate 2-3 per review) |
| Config (`config/config.yaml`) | Suboptimal settings, unused options, missing features | Weekly |
| Vault structure (Obsidian) | Recent modifications as automation signals, stale content, missing docs | Weekly |
| HEARTBEAT.md itself | Stale standing orders, missing checks, optimization opportunities | Weekly + daily mini |
| Vault recent activity | Recently created/modified files — "things done" as automation candidates | Weekly |

## Open Questions

1. **Daily mini-review time window:** Should it fire at a specific time (e.g., afternoon when there's enough activity to review) or just on any full-scan cycle? Leaning toward: first full-scan after 14:00 each day.
2. **Vault activity scanning:** What's the right way to detect recent Obsidian changes? `find` with mtime? Git history if the vault is version-controlled? Just `ls -lt` on key directories?
3. **Proposal volume cap:** Should there be a max proposals per review (e.g., 3 per weekly, 1 per daily mini) to avoid overwhelming Scott? Or just let it propose freely and Scott can ignore what's not useful?

## What's NOT in Phase 3

- Obsidian Inbox processing (Phase 3b)
- Inbox routing rules / `inbox-rules.md` (Phase 3b)
- Autonomous actions beyond current Tier 2 permissions (deferred)
- Reaction-based or command-based proposal approval
- Auto-approve escalation for rules
