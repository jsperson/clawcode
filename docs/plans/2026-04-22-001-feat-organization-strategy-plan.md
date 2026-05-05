---
title: "feat: ClawCode + Vault Organization Strategy"
type: feat
status: active
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-organization-strategy-requirements.md
---

# feat: ClawCode + Vault Organization Strategy

## Overview

Three months into daily use, ClawCode's memory, scheduler, and Obsidian vault are showing entropy: entity pages have duplicate timeline entries, some scheduled jobs have stalled silently, archive state is ambiguous, and there's no way to measure whether changes help or hurt retrieval. This plan fixes quality issues in-place, establishes a retrieval benchmark to make future changes measurable, and prunes dead config — without adding new surface area.

**Origin:** `docs/brainstorms/2026-04-22-organization-strategy-requirements.md`

## Decisions Made (Session 2026-04-22)

**Schedule dispositions (10 active jobs):**

| Job | Disposition |
|---|---|
| daily_backup | Keep as-is |
| life_overnight | Keep as-is |
| weekly_trends | Keep — investigate W17 (2026-04-20) miss |
| daily_scout | **Change** — move to weekly cadence; sharper "worth acting on" framing |
| weekly_experiment | **Change** — trigger from scout findings instead of fixed weekly |
| daily_summary | Keep as-is (Scott reads them) |
| entity_graph | Keep — patch quality issues in place |
| compound_plugin_check | Keep as-is |
| life_evening | Keep — investigate stall since 2026-04-15 |
| life_evening_fallback | Keep — fix alongside life_evening |

**Disabled job cleanup:** Delete `daily_digest`, `inbox_check`, `reminder_check` from `config/schedules.yaml`.

**Strategy decisions:**
- Entity graph fix: **patch in place** (no GBrain-style rewrite this cycle)
- Signal detector: **surface-only** (no auto-mutation)
- Retrieval benchmark: **build first** to establish baseline before entity work
- New surface area: **conservative** — no new scheduled jobs this cycle

## Scope Boundaries

**In scope:**
- Retrieval benchmark suite (establish baseline)
- Entity graph quality patches (dedup, sort, alias resolution)
- Scheduler config cleanup (delete 3 dead jobs, re-cadence 2)
- Diagnose + fix life_evening and weekly_trends stalls
- Signal detector that writes a read-only report
- Scout prompt improvement + scout→experiment trigger link
- Archive audit pass (identify orphaned project folders)

**Out of scope (explicit non-goals):**
- GBrain-style rewrite of entity graph
- Any new scheduled job
- Autonomous mutation of vault/memory contents
- Multi-user / Marshal platform work (separate project)
- New dashboards or digest feeds

## Implementation Units

Phases sequence to preserve measurability: benchmark before entity changes, config cleanup before stall fixes (isolate variables), signal detector last (needs everything else stable).

---

### Phase 1 — Scheduler Config Cleanup

#### Unit 1.1: Delete dead schedule entries
**Goal:** Remove `daily_digest`, `inbox_check`, `reminder_check` from config so the file reflects reality.

**Files:**
- Modify: `config/schedules.yaml`

**Approach:**
- Remove the three disabled entries entirely (including associated prompt/script blocks)
- Verify no launchd plist files reference them; delete orphaned plists if found under `~/Library/LaunchAgents/`

**Verification:**
- `grep -E "daily_digest|inbox_check|reminder_check" config/schedules.yaml` returns nothing
- `clawcode schedule list` shows only the 10 active jobs

---

#### Unit 1.2: Re-cadence daily_scout → weekly
**Goal:** Change `daily_scout` from `0 4 * * *` to weekly (propose Sunday 04:00 so it feeds Monday's trends/experiments).

**Files:**
- Modify: `config/schedules.yaml` (cron expression, job name optional — consider renaming to `weekly_scout`)
- Modify: scout prompt body in `config/schedules.yaml` — add explicit "raise 1-3 specific improvement suggestions for ClawCode, the vault, or Scott's workflow; cite what triggered them"
- Modify: output path convention from `life-agent/scouting/YYYY-MM-DD.md` → `life-agent/scouting/YYYY-WNN.md`

**Approach:**
- Keep the job name as `daily_scout` OR rename to `weekly_scout` — Scott's call during implementation. If renamed, search for references in skills and docs.
- Archive existing daily scouting files? Defer — they don't break anything sitting in the folder.

**Verification:**
- Next Sunday's scout report exists at the new path
- Report contains an "Improvement Suggestions" section with at least one concrete recommendation tied to a scouted finding

---

#### Unit 1.3: Link weekly_experiment to scout findings
**Goal:** `weekly_experiment` reads the most recent scout report and picks experiments from its improvement suggestions rather than generating speculatively.

**Files:**
- Modify: `config/schedules.yaml` — weekly_experiment prompt
- Reference: latest `life-agent/scouting/YYYY-WNN.md`

**Approach:**
- Update the experiment prompt to: "Read the most recent `life-agent/scouting/YYYY-WNN.md`. Pick 1-2 improvement suggestions with enough concrete signal to test in a Docker container. If the scout report has no testable suggestions, skip this week and post that to Discord."
- Cadence stays Wednesday 04:00 (lets Sunday scout → Wednesday experiment pipeline work)

**Verification:**
- Next weekly_experiment run's output references a specific scout suggestion as its source
- If no testable suggestion exists, Discord posts the skip message rather than running a speculative experiment

---

### Phase 2 — Retrieval Benchmark Baseline

#### Unit 2.1: Build benchmark query suite
**Goal:** A small, curated set of queries with expected results that can be re-run before and after every memory/entity change to measure retrieval quality.

**Files:**
- Create: `tests/retrieval/benchmark.yaml` — query + expected top-N files/entities
- Create: `tests/retrieval/run_benchmark.py` (or shell script) — runs each query through QMD and FTS5, compares to expected, emits score
- Create: `tests/retrieval/README.md` — how to add queries, how to interpret scores

**Approach:**
- Seed with 15-20 queries covering:
  - Entity recall (e.g., "what did David Cochran and I discuss about Marshal")
  - Project retrieval ("what's the status of DockerClawCode")
  - Conversation recall ("what did I decide about GBrain multi-user")
  - Cross-reference ("who is John McElligott")
  - Stale/broken link detection ("find pages that reference deleted entities")
- Score function: precision@5 for top-N matches, separate scores for QMD vector, QMD keyword, FTS5
- Output: JSON scorecard with per-query hits/misses + aggregate

**Test scenarios:**
- Happy path: known-good query returns expected entity on page 1
- Edge: query with typo/alias (Marshall vs Marshal) — measures alias resolution
- Negative: query for nonexistent content returns empty, not false positives
- Regression: run baseline twice in a row, verify deterministic results

**Verification:**
- `python tests/retrieval/run_benchmark.py --baseline` writes a dated scorecard
- Scorecard contains scores for all queries across all three search surfaces
- Baseline committed to repo so Phase 3+ changes can compare against it

---

### Phase 3 — Entity Graph Quality Patches

#### Unit 3.1: Audit current entity state
**Goal:** Understand how bad the damage is before patching.

**Files:**
- Create: `scripts/audit_entities.py` (or markdown generator) — one-shot audit script
- Output: `docs/audits/2026-04-entity-audit.md`

**Approach:**
- Walk `Entities/**/*.md`
- Count: duplicate timeline entries (exact-match lines within same date section), out-of-order dates, entities with near-duplicate canonical names (Marshal/Marshall), entities with broken relationship links
- Report top offenders, total issue counts, sample fixes

**Verification:**
- Audit report lists at minimum: David-Cochran.md duplicates, Marshal vs Marshall split, any other near-duplicates
- Report is the baseline for measuring patch effectiveness

---

#### Unit 3.2: Timeline dedup + chronological sort
**Goal:** Fix the daily entity_graph prompt so it (a) deduplicates timeline entries within a date section before appending and (b) sorts timeline sections in descending chronological order.

**Files:**
- Modify: the entity_graph prompt in `config/schedules.yaml`
- Possibly: a post-processing step — script that runs after the agent, reads the entity file, dedups + sorts, writes back

**Approach:**
- Option A: Strengthen prompt with explicit dedup + sort instructions + examples
- Option B: Add a deterministic post-process script that handles formatting (preferred — prompts drift, scripts don't)
- Go with Option B: prompt produces content, script normalizes structure

**Test scenarios:**
- Happy: entity page with 3 duplicate lines under 2026-04-21 → dedup leaves 1
- Happy: entity with sections in order [2026-03-06, 2026-04-21, 2026-02-23] → reorders to [2026-04-21, 2026-03-06, 2026-02-23]
- Edge: single-entry timeline — no-op
- Edge: date section with 1 unique + 3 near-duplicate phrasings — prompt should already consolidate before write; dedup as safety net

**Verification:**
- Re-run audit (Unit 3.1) after one entity_graph cycle — duplicate count drops to ~0, chronological ordering clean
- David-Cochran.md specifically: the 4x "Has an AI vision that Chris Wyant is enthusiastic about" collapses to 1 entry

---

#### Unit 3.3: Alias resolution — Marshal vs Marshall
**Goal:** Merge split entities created by typo/capitalization variants.

**Files:**
- Modify: entity_graph prompt — add alias lookup step before creating new entity files
- Modify: `Entities/Projects/Marshal.md` (merge target, has proper aliases frontmatter)
- Delete: `Entities/Projects/Marshall.md` (if it exists as a separate file)
- Modify: any file that links to `Marshall` — redirect to `Marshal`

**Approach:**
- Before writing a new Entities file, the extractor should grep existing entities' `aliases:` frontmatter + canonical_name for fuzzy matches
- Add "Marshall" to Marshal.md's aliases list to prevent re-splitting
- Add similar alias-lookup logic for other common confusions (verify during Unit 3.1 audit — may find others)

**Test scenarios:**
- Happy: extractor encounters "Marshall" in a log → resolves to Marshal.md instead of creating new file
- Edge: genuinely different entity with same name — extractor needs an escape hatch (proper noun + context should usually disambiguate; if ambiguous, flag in Signal Detector output rather than silently merging)

**Verification:**
- `ls Entities/Projects/ | grep -i marshal` shows exactly one file
- `grep -r "Marshall" Entities/` returns references only in the aliases list
- Benchmark query "what did David and I discuss about Marshal" — recall improves vs baseline

---

### Phase 4 — Stall Diagnostics + Fixes

#### Unit 4.1: Diagnose life_evening stall
**Goal:** Figure out why no evening reviews have been generated since 2026-04-15 despite the job being enabled.

**Files:**
- Read: `~/Library/LaunchAgents/com.clawcode.life_evening.plist`
- Read: launchd stdout/stderr logs for that agent (path in plist)
- Read: recent `memory/YYYY-MM-DD-cli.md` for 20:00 attempts
- Read: `life-agent/reviews/daily/` (confirm Apr 15 was last)

**Approach:**
- Check if launchd even fires the job (log timestamps)
- Check if job fires but produces no file (Discord prompt succeeds but user doesn't respond, and fallback also fails?)
- Check if Discord delivery is the broken link
- Check if the `/life:evening` skill itself errors

**Verification:**
- Root cause documented in a short note (could be daily log entry, not its own file)
- Fix committed — OR, if root cause is "Scott stopped engaging with Discord prompt", confirm fallback path works by forcing a dry run

---

#### Unit 4.2: Fix life_evening + fallback
**Goal:** Restore daily evening review output, even on nights Scott doesn't engage.

**Files:**
- Probably: `skills/life-agent/review/` or wherever the evening-review skill lives
- Possibly: `config/schedules.yaml` — fallback prompt tweak

**Approach:**
- Apply fix identified in 4.1
- Force a single manual run to verify: `clawcode schedule run life_evening_fallback`
- Verify file lands at `life-agent/reviews/daily/YYYY-MM-DD.md`

**Verification:**
- Next scheduled 20:00 run produces a review file (interactive or fallback)
- Fallback works independently — confirmed by manual trigger producing output without Discord interaction

---

#### Unit 4.3: Diagnose weekly_trends W17 miss
**Goal:** Understand why weekly_trends didn't fire on Monday 2026-04-20 despite machine being up.

**Files:**
- Read: launchd plist + logs for `com.clawcode.weekly_trends`
- Read: `Trends/2026-W17.md` — confirm it's missing (already known)
- Read: catchup coordinator logs (if any exist)

**Approach:**
- Same diagnostic pattern as 4.1
- Fix: could be launchd config, could be prompt/script error, could be catchup logic bug
- If fix requires rerunning W17 now, do so manually once

**Verification:**
- W17 trends file exists (via manual rerun if needed)
- Next Monday (W18 or later) runs successfully with no intervention
- Root cause documented

---

### Phase 5 — Signal Detector (Surface-Only)

#### Unit 5.1: Build signal detector report
**Goal:** A read-only audit that flags stale memory topics, broken entity links, orphaned projects, and other drift signals — writes to a report Scott reads, does not auto-fix.

**Files:**
- Create: `scripts/signal_detector.py` (or similar)
- Create: `config/schedules.yaml` entry — **deferred**. Per conservative-stance decision, run manually for now; add to schedule only after 2-3 successful manual runs prove value.
- Output: `life-agent/signals/YYYY-MM-DD-signals.md`

**Approach:**
Detect at minimum:
- **Stale memory topics** — topic files in `~/clawcode/memory/topics/` not updated in >60 days
- **Broken entity links** — `[Name](path.md)` references in Entities/ that don't resolve
- **Orphaned projects** — `Projects/*/` folders with no README, no recent file modification (>90 days), not in Archive
- **Duplicate-looking entities** — near-matching canonical names across Entities/ (flags Marshal/Marshall style splits before they cause damage)
- **Stalled schedules** — jobs with no output in >2x their expected cadence

**Test scenarios:**
- Happy: known broken link planted in test fixture → detector reports it
- Edge: intentionally stale file (e.g., `personal.md` if Scott said "this is stable, don't flag") — needs an ignore mechanism (allowlist in the script? `---ignore_signal: true` frontmatter? defer the exact mechanism to implementation)
- Regression: re-run on clean state returns empty findings

**Verification:**
- Manual run produces signals report
- Report is readable in 5 minutes — not a flood of noise
- Report's findings, if acted on, would measurably improve benchmark scores

---

### Phase 6 — Archive Audit

#### Unit 6.1: Identify orphaned project folders
**Goal:** Resolve the "archive state ambiguous" gap — find projects that are clearly done/abandoned but still sit in `Projects/`.

**Files:**
- Create: `docs/audits/2026-04-archive-audit.md` — findings document
- No code changes — pure audit + manual classification pass

**Approach:**
- List every folder under `Projects/` with: last modified date of any file, most recent README mention, entity graph references
- Classify each: active, needs-archive, unclear-ask-Scott
- For "needs-archive", prepare a single batch move to `Archive/` pending Scott's approval (do not auto-move)

**Verification:**
- Audit document lists every `Projects/*/` folder with classification
- Scott reviews, confirms the archival set, implementer executes the moves

---

## Sequencing + Dependencies

```
Phase 1 (config cleanup)     → parallelizable, low risk, do first
Phase 2 (benchmark baseline) → BLOCKS Phase 3 verification (need baseline)
Phase 3 (entity patches)     → depends on Phase 2 for measurement
Phase 4 (stall fixes)        → independent of Phase 2/3, can run parallel to either
Phase 5 (signal detector)    → depends on Phase 3 (needs clean entities to audit meaningfully)
Phase 6 (archive audit)      → independent, can run anytime
```

**Recommended order:** Phase 1 → Phase 2 → Phase 4 (parallel) → Phase 3 → Phase 6 (parallel) → Phase 5.

## Risks

1. **Post-process script breaks entity file formatting.** Mitigation: audit-first approach (Unit 3.1), dry-run mode before live writes, benchmark catches regressions.
2. **life_evening root cause is something subtle** (e.g., Discord rate limits, Claude Code session contention). Mitigation: Unit 4.1 is pure diagnostic — we learn before we fix. If fix is non-trivial, scope-cut to fallback-only mode.
3. **Benchmark queries don't represent real usage.** Mitigation: seed from Scott's actual recent conversation patterns; iterate based on which queries produce surprising scores.
4. **Signal detector flood.** First run will likely surface 50+ findings because the system has been accumulating entropy for 3 months. Mitigation: report groups by severity; initial pass is a one-time cleanup, not ongoing noise.

## Deferred to Implementation

- Exact signal-detector ignore mechanism (allowlist vs frontmatter)
- Whether post-process script is Python or shell
- Whether `daily_scout` renames to `weekly_scout` or keeps its name
- Retention policy for existing daily scouting files (delete vs leave)

## Open Questions (None Blocking)

None — all planning questions resolved in the 2026-04-22 session.

## Success Criteria

1. **Measurable improvement:** Post-Phase-3 benchmark scores > Phase-2 baseline on at least 70% of queries.
2. **Config reflects reality:** `config/schedules.yaml` contains exactly the 10 active jobs, zero disabled entries.
3. **No silent stalls:** life_evening and weekly_trends produce output on their next scheduled runs.
4. **Entity pages don't embarrass:** David-Cochran.md (and peers) show clean, deduplicated, chronologically sorted timelines.
5. **Signal detector is actionable:** First run surfaces the known issues (stale topics, broken links, Marshal/Marshall) without burying them in noise.
