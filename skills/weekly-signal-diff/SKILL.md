---
name: weekly-signal-diff
description: >
  Weekly structural change analysis across AI, macro economics, geopolitics,
  financial stability, and markets. Use when user asks "run my weekly signal
  diff", "what changed this week", "weekly trends", "macro trends", or
  "weekly review".
---

# Weekly Signal Diff

## Problem

A wall of news does not tell the user what structurally changed. Most weekly roundups over-index on headlines, underweight economics and dependency shifts, and ignore what the user actually cares about. This skill turns a noisy week into a small set of structural changes, weighted by personal context.

## When to Use

- Weekly macro trends journal entry (scheduled Mondays at 03:00)
- "Run my weekly signal diff"
- "What changed this week that matters to me?"
- "Weekly trends"

## Required Context

Gather as much as the environment allows:

- The user's active projects, priorities, and recurring interests
- Prior weekly diffs from `Trends/` in the Obsidian vault (read last 2-4 entries)
- The desired freshness window (default: last 7 days)
- Any preferred outlets, banned sources, or explicit watchlist entities

If the user has not provided categories or companies, read `references/starter-universe.md` and use it as a bootstrap layer only.

If live web access is available, read `references/live-search-upgrade.md` and use the strongest search mode the environment supports.

## Process

1. **Establish the frame.**
   - Confirm the topic space, freshness window, and whether the goal is personal awareness, operator strategy, investor tracking, or content prep.
   - If running as a scheduled job with no user input, default to a 7-day operator-style review across all domains.

2. **Pull personal context first.**
   - Search QMD for active projects, current priorities, recurring entities, and recent captures.
   - Read the last 2-4 weekly diffs from `Trends/` to understand thread continuity.
   - Extract a short relevance profile: what the user is building, what they keep revisiting, what they are worried about, and what they are trying to learn.

3. **Build the watchlist.**
   - Start from the starter universe if the user has not defined a watchlist.
   - Treat the starter list as a scaffold, not a contract.
   - Re-rank or replace items using personal context:
     - promote companies, categories, or themes that appear in active projects or recent conversations
     - demote low-signal items
     - add personal-priority entities even if they are outside the starter set
   - Preserve some baseline discovery. Personalization should shape the scan, not collapse it into only known favorites.

4. **Gather the week's evidence.**
   - Perform a broad web search sweep across all domains, then targeted follow-ups on the top candidate shifts.
   - Prefer fresh, source-backed information with links or citations.
   - If web search is not available, work from provided sources and say the diff is source-bounded.
   - Ignore pure announcement theater unless it changes economics, distribution, regulation, dependency, geography, or buyer behavior.

5. **Ask the structural questions on every candidate signal.**
   - What constraint shifted?
   - Who gained or lost leverage?
   - What got cheaper, harder, faster, or more defensible?
   - What dependency got exposed?
   - What business model or pricing assumption weakened?
   - What changed in regulation, geography, or distribution?
   - Why does this matter for the user's actual projects, workflows, or situation?

6. **Score before writing.**
   - Keep only the signals that represent real structural change.
   - A good weekly diff has 3-7 structural shifts per domain, fewer if the week was quiet.
   - Merge duplicates, drop weak stories, and explicitly label speculation as speculation.

7. **Produce the weekly diff.**

   Write to the Obsidian vault at:
   `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Trends/YYYY-WNN.md`

   Use this structure (matching the established format):

   ```markdown
   # Week NN, YYYY (Mon DD - Mon DD)

   ## Summary
   2-4 sentence overview of the week's dominant structural shifts.

   ---

   ## 🌍 Geopolitics
   Power shifts, trade policy, conflict, alliances, sanctions.
   Include threads tagged #thread/[name] for continuity.

   ---

   ## 📈 Economics
   Growth indicators, monetary policy, labor markets, inflation.
   Include catalyst calendar with upcoming dates.

   ---

   ## 🤖 Technology
   AI models, infrastructure, platforms, developer tools, adoption patterns.
   Include bubble watch / capex-to-revenue metrics.

   ---

   ## 💰 Financial Stability
   Banking stress, credit spreads, sovereign/EM risk, treasuries.

   ---

   ## 📊 Market Volatility Signals
   VIX/VVIX/skew, dealer gamma, options flow, cross-asset warnings, catalyst calendar.

   ---

   ## 💳 Consumer Credit Health
   Card delinquencies, charge-offs, FICO distribution, auto/mortgage stress.

   ---

   ## 🃏 Wildcards
   Cross-cutting or unexpected developments that don't fit a domain.

   ---

   ## Questions to Track
   5-8 forward-looking questions for the coming week(s).

   ---

   ## Thread Index
   - #thread/name — description (NEW / cont. from WNN / resolved)

   ---

   ## Sources
   List all sources consulted with dates.
   ```

   **Tags to use within entries:**
   - `#signal` — Early indicator, not yet mainstream
   - `#narrative-shift` — Consensus view changing
   - `#contrarian` — Counter to dominant narrative
   - `#confirmed` — Previously noted trend now validated
   - `#thread/[name]` — Cross-week tracking thread

8. **Diff against prior weeks.**
   - For each active thread from the prior week's Thread Index, explicitly state: continued, escalated, de-escalated, or resolved.
   - New threads get tagged `(NEW)`.
   - Threads with no new signal get tagged `(quiet this week)`.
   - This is what makes it a diff, not a digest.

9. **Post summary.**
   - Post a brief summary to the main session when complete.
   - Format: "Weekly Signal Diff W{NN} written to Trends/. Top shifts: [2-3 sentence summary]."

## Guardrails

- The goal is **diff, not digest**.
- Do not force all starter universe entities into the final output. They prevent blank-page syndrome, not create fake coverage.
- Do not mistake product launches, benchmark screenshots, or funding headlines for structural change unless they move a real constraint.
- Keep general analysis separate from personalized implications.
- If evidence is thin in a domain, say the week was thin. Do not pad.
- If web search is unavailable, be explicit about the freshness limitation.
- If the user's interests are unclear, use the starter universe and explain it is a bootstrap pass.
- Preserve thread continuity — the Thread Index is the most valuable part of the system over time.

## Notes for Scheduled Runs

- When invoked by the scheduler (no interactive user), skip the frame-setting step and default to a full 7-day operator review across all domains.
- Read the last 2 entries from `Trends/` for thread continuity.
- Search QMD with `collection: "vault-main"` for active project context.
- Write the output file, then post the summary.
