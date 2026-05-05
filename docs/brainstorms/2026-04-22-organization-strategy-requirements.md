# ClawCode + Vault Organization Strategy — Requirements

**Date:** 2026-04-22
**Owner:** Scott Person
**Status:** Brainstorm — pending decisions

## Problem

After ~3 months of compounding use, the ClawCode + Obsidian vault system is solid but showing entropy. The audit identified five organization-quality gaps; separately, several scheduled jobs may be running without pulling weight. Rather than fix these piecemeal, this doc captures a unified strategy covering **organization improvements + schedule rationalization + rollout sequence** so the work compounds instead of churning.

**Goal:** Get to "excellent" on organization. Cut scheduled work Scott doesn't use. Add scheduled work that closes feedback loops.

**Non-goal:** Rebuilding the whole system. Preserve what works (persona files, vault structure, Apple Reminders for tasks, notes-inbound pipeline).

## Current State Inventory

### Five organization gaps (from 2026-04-22 audit)

1. **Entity graph quality** — 310 pages, but noisy: duplicate timeline entries, unordered timelines, split entities (Marshal/Marshall), untyped relationships.
2. **Memory curation** — 138 total lines across 4 topic files vs 60+ days of raw daily logs. Signal-to-curation ratio is lopsided. No passive signal detector mining the logs.
3. **Memory freshness** — MEMORY.md has stale claims ("Project Momentum" 10 days old, "removed from tracking" items still listed in SKILL.md). No enforced audit.
4. **Archive state ambiguity** — can't distinguish completed / stalled / imported. No archival dates, no reasons.
5. **No retrieval quality metrics** — QMD works, but we don't measure whether it's getting better or worse.

### Scheduled jobs inventory (state as of 2026-04-22)

| Job | Cron | Status | Output | Used? |
|---|---|---|---|---|
| `daily_backup` | 01:00 daily | ✅ healthy | `clawcode ≈63MB + claude ≈525MB → iCloud` | **Yes** — load-bearing insurance |
| `life_overnight` | 02:00 daily | ✅ healthy | `life-agent/plans/daily/YYYY-MM-DD.md` | **Unknown** — plans exist through today |
| `life_evening` | 20:00 daily | ⚠️ **stalled** | Last review: **2026-04-15** (7 days ago) | **?** — was producing, now isn't |
| `life_evening_fallback` | (related) | ⚠️ stalled | Same | Same |
| `daily_scout` | 04:00 daily | ✅ healthy | `data/scouting/YYYY-MM-DD.md` | **?** — feeds weekly_experiment |
| `daily_summary` | 06:30 daily | ✅ healthy | `memory/YYYY-MM-DD-summary.md` (Apr 22 exists) | **Scott said: rarely** |
| `entity_graph` | 07:00 daily | ✅ healthy | `Entities/*/` pages (but quality issues — see gap #1) | **Yes** — but noisy |
| `compound_plugin_check` | Tue 09:00 | ✅ healthy | Log-only output; summarized to Discord | **?** |
| `weekly_trends` | Mon 03:00 | ⚠️ **missed W17** | `Trends/YYYY-WNN.md` (last: W16 = Apr 13) | **?** — didn't fire Apr 20 |
| `weekly_experiment` | Wed 04:00 | ✅ healthy | `data/scouting/experiments/` + `proposals/` | **?** |
| `daily_digest` | 07:00 daily | 🚫 **disabled** | Would go to `Digests/Daily/` (last: Feb) | N/A |
| `inbox_check` | every 30min | 🚫 disabled | — | N/A |
| `reminder_check` | hourly | 🚫 disabled | — | N/A |

**Two anomalies to investigate independently:**
- `life_evening` produced nothing after 2026-04-15. Plans still generate overnight but the evening review isn't landing.
- `weekly_trends` didn't fire on Mon 2026-04-20 at 03:00 despite the machine being up (machine was down Apr 17-18, but not Apr 20).

## What "Excellent" Looks Like

1. **Entity graph is clean.** No duplicates, timelines in reverse-chron order, typed relationships where possible, merged split entities.
2. **Daily logs compound into curated memory automatically.** A signal detector runs daily and proposes memory/topic updates — Scott approves or ignores.
3. **Memory stays fresh.** A weekly audit flags stale claims, drift between SKILL.md and reality, broken cross-references.
4. **Archive tells a story.** Every archived project has a reason (done / stalled / abandoned / imported) and a date.
5. **Retrieval quality is measured.** Small benchmark runs weekly; regressions show up in the weekly trends or digest.
6. **Every scheduled job earns its keep.** Jobs Scott doesn't use are cut. Jobs that produce output nobody reads are cut or redirected.

## Proposed Scope

### Work block A — Schedule rationalization (cut first, build on cleaner base)

Decide per-job: **keep / cut / enhance**. Candidates for cutting:

- **`daily_summary`** — Scott said rarely used. But summaries feed QMD for semantic search. Cut recommendation: **downgrade to weekly**, or **cut entirely** if QMD search directly over raw logs is good enough.
- **`life_evening`** (stalled Apr 15) — do we resuscitate or retire? If Scott doesn't look at reviews, retire.
- **`life_overnight`** — same question. If plans aren't used, retire.
- **`daily_scout` + `weekly_experiment`** — scout feeds experiment. If experiments produce proposals Scott doesn't read, cut the chain.
- **`compound_plugin_check`** — Tuesday check on plugin repo. Useful, but check Discord summary shows up — if ignored, cut.
- **`weekly_trends`** — Scott uses these for macro awareness. Keep, but fix the Mon 2026-04-20 miss.

**Keeps no matter what:**
- `daily_backup` — insurance.
- `entity_graph` — core memory infrastructure (needs quality work separately).

**Additions proposed:**
- **`signal_detector`** (new) — mines yesterday's daily logs for ideas, decisions, entity mentions; drafts memory/topic updates for Scott to accept. Daily at 06:45 (after summary, before entity_graph).
- **`memory_audit`** (new) — weekly check on MEMORY.md freshness, SKILL.md drift, broken cross-references. Sunday 06:00.
- **`retrieval_benchmark`** (new) — runs small "questions I should be able to answer" test weekly. Sunday 06:30.

### Work block B — Entity graph quality (highest leverage on biggest surface)

1. **Dedup pass** — merge split entities (Marshal + Marshall), collapse duplicate timeline entries, reconcile aliases.
2. **Timeline ordering** — reverse-chronological consistently; one entry per event.
3. **Typed relationships (subset)** — extract `works_at`, `attended`, `created`, `contributed_to` from existing relationship prose where cheap. Don't over-invest; gbrain's zero-LLM regex is a next-phase option.
4. **Update `entity-graph.py`** — fix the root cause (duplicate generation) so cleanup doesn't need to rerun.

### Work block C — Memory freshness + signal detector

1. **Signal detector skill** — reads yesterday's `*-discord.md` and `*-cli.md` logs, extracts decisions / new entities / stated preferences / ideas. Writes a `memory/pending/YYYY-MM-DD-signals.md` draft. Scott accepts / ignores / edits.
2. **Memory audit skill** — scans MEMORY.md, topic files, and SKILL.md cross-references. Flags: stale dated claims, files referenced that don't exist, folder paths that don't match reality.
3. **Fix current drift** — one-time cleanup pass on MEMORY.md (the "Project Momentum" section) and `scott-vault/SKILL.md` (Browser-Automation, Pi4to3-Migration phantom folders).

### Work block D — Archive state model

1. **Add frontmatter to archived projects** — `archived_date`, `archive_reason: completed | stalled | abandoned | imported`.
2. **One-time cleanup of existing archive** — categorize ~20 current entries (AI-Prompt-Championship = completed, Browser-Automation = abandoned, etc.).
3. **Project lifecycle skill** — when moving Projects/ → Archive/, prompt for reason + date.

### Work block E — Retrieval benchmark

1. **Question set** — 20-30 "I should be able to answer this" questions across domains (who is X, when did Y happen, what tool did I use for Z, what's my preference on W).
2. **Scoring** — weekly script runs each question through QMD + evaluates the result. Binary pass/fail per question, rolling accuracy over time.
3. **Regression alerts** — if weekly accuracy drops >10%, flag in Discord.

## Sequencing (Recommendation)

**Phase 1 — Cut the dead weight (this week, 1-2 sessions):**
1. Inventory which schedule outputs Scott actually reads (needs Scott's input below).
2. Disable or cut the chosen jobs.
3. Fix `life_evening` stall and `weekly_trends` miss root causes OR cut those too.

**Phase 2 — Entity graph cleanup (next, ~2 sessions):**
1. Dedup + timeline ordering pass.
2. Fix `entity-graph.py` root cause.
3. Merge Marshal/Marshall.

**Phase 3 — Signal detector + memory audit (after Phase 2, 1 session each):**
1. Draft signal-detector skill.
2. Draft memory-audit skill.
3. Add both to schedule.

**Phase 4 — Archive state model + retrieval benchmark (parallel, low urgency):**
1. Archive frontmatter + one-time cleanup.
2. Benchmark question set + scoring.

## Open Decisions for Scott

These are the calls Scott needs to make before planning turns into building:

### A. Which scheduled outputs do you actually read?

For each, mark: **read regularly / skim occasionally / never / didn't know it existed**.

| Output | Path |
|---|---|
| Life daily plan | `life-agent/plans/daily/YYYY-MM-DD.md` |
| Life daily review | `life-agent/reviews/daily/YYYY-MM-DD.md` |
| Daily log summary | `memory/YYYY-MM-DD-summary.md` |
| Weekly trends | `Trends/YYYY-WNN.md` |
| Daily scout report | `data/scouting/YYYY-MM-DD.md` |
| Weekly experiment report | `data/scouting/experiments/` |
| Proposals | `proposals/*.md` |
| Compound plugin check | Discord summary on Tuesdays |

### B. Cut aggressive or cut conservative?

- **Aggressive:** disable anything not read regularly, even if "might be useful someday."
- **Conservative:** keep anything that might eventually matter; accept some dead weight.

### C. Signal detector autonomy level

- **Propose only:** drafts go to `memory/pending/`, Scott reviews and accepts.
- **Auto-apply low-risk:** new entity mentions auto-created; decisions/preferences require approval.
- **Full auto:** everything auto-applied, Scott audits weekly.

### D. Entity graph: full rewrite of `entity-graph.py` or incremental fixes?

The current script generates duplicates and scrambled timelines. Fix options:
- **Incremental:** patch the script + run `--regenerate` to rewrite all compiled truths. Keeps history, fixes output.
- **Rewrite:** start cleaner, apply gbrain-style patterns (compiled-truth + timeline + typed links). More work, better endgame.

### E. Retrieval benchmark: build now or defer?

Benchmark is the lowest-urgency work and only pays off if we're changing memory infrastructure regularly. Options:
- **Build with Phase 3** (alongside signal detector) so we measure the change
- **Defer to Phase 5** (only build once we have something to measure)

## Success Criteria

**After Phase 1 (cut):**
- Scheduled job count drops by 3-5
- Every remaining job has a named consumer (Scott, a downstream skill, or a retention rule)
- No stalled jobs (`life_evening` fixed or cut)

**After Phase 2 (entity graph):**
- Zero duplicate timeline entries in sampled entities
- Zero split entities (no Marshal + Marshall)
- Timelines in reverse-chron order

**After Phase 3 (signal + audit):**
- Daily signal proposals landing in `memory/pending/`
- Weekly memory audit catching drift before Scott does
- MEMORY.md and SKILL.md in sync

**After Phase 4 (archive + benchmark):**
- Every archived project has a reason + date
- Weekly retrieval accuracy score posted to Discord
- Benchmark regressions flagged within 7 days

## Non-Goals

- Full gbrain port (typed graph + compiled-truth + hybrid search). Captured patterns, not a wholesale rewrite.
- Multi-user support (ClawCode is single-user by design).
- Migrating off QMD. It works.
- Rewriting notes-inbound, scott-vault, or persona files. Those are good.

## Dependencies / Risks

- **`life_evening` stall root cause** must be diagnosed before cut/keep decision — it may indicate a broken integration worth preserving.
- **`entity-graph.py` rewrite** risks losing history if the regeneration isn't careful. Mitigation: backup `Entities/` before running.
- **Signal detector false positives** could clutter memory. Mitigation: start with "propose only" mode.
- **Scope creep** — the five gaps + schedule rationalization is already big. Guard against adding new scope until Phase 1 lands.

## References

- `skills/scott-vault/SKILL.md` — vault structure
- `skills/weekly-signal-diff/SKILL.md` — pattern for scheduled analysis
- `config/schedules.yaml` — current schedule definitions
- `MEMORY.md` — current memory index
- `Projects/Marshal/` — separate but related (David's project; shares concerns about memory + organization)
- GBrain (`github.com/garrytan/gbrain`) — pattern source for compiled-truth + typed graph
