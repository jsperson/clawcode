# Entity Graph Audit — 2026-04

Read-only audit of `Entities/**/*.md` to quantify quality issues
before patching `scripts/entity-graph.py`.

## Summary

- **Entities scanned:** 309
- **Total timeline bullets:** 2353
- **Exact-duplicate bullets (within a date section):** 162 across 47 entities
- **Near-duplicate bullets (ratio ≥ 0.85):** 232 across 52 entities
- **Entities with out-of-order date sections:** 52
- **Entities with broken relationship links:** 1
- **Filename / canonical-slug mismatches:** 2
- **Near-duplicate canonical names (ratio ≥ 0.88):** 2

## Top offenders — timeline duplication

| Entity | Dates | Bullets | Exact dups | Near dups |
|---|---|---|---|---|
| `Entities/Projects/ClawCode.md` | 49 | 280 | 38 | 36 |
| `Entities/Projects/Life-Agent.md` | 30 | 151 | 15 | 25 |
| `Entities/Projects/AI-Competition-Oracle.md` | 6 | 90 | 14 | 21 |
| `Entities/Tools/Hermes-Agent.md` | 11 | 38 | 8 | 11 |
| `Entities/Tools/Canvas.md` | 16 | 50 | 3 | 12 |
| `Entities/Organizations/Cornerstone.md` | 3 | 42 | 5 | 8 |
| `Entities/Projects/OpenClaw.md` | 22 | 67 | 6 | 6 |
| `Entities/Tools/Claude-Code.md` | 24 | 73 | 3 | 9 |
| `Entities/Projects/AI-Prompt-Championship.md` | 18 | 67 | 6 | 5 |
| `Entities/Tools/QMD.md` | 13 | 35 | 3 | 6 |

### Sample near-duplicate pairs from `Entities/Projects/ClawCode.md`

- **2026-02-24**
  - `Discord + CLI deemed sufficient — multi-channel gateway is not a gap`
  - `Discord + CLI confirmed as sufficient — multi-channel gateway is not a gap`
- **2026-02-24**
  - `Native ephemeral Task-based subagent model confirmed as better fit than OpenClaw's persistent subagent architecture`
  - `ClawCode's native ephemeral Task-based subagent model was concluded to be a better fit than OpenClaw's persistent subagent architecture.`
- **2026-02-23**
  - `AskUserQuestion tool fails in Discord bot's non-interactive environment`
  - `AskUserQuestion tool does not work in the Discord bot's non-interactive environment`

## Near-duplicate canonical names

| Entity A | Entity B | Similarity |
|---|---|---|
| `People/Lilly` | `People/Lily` | 0.89 |
| `Tools/Apple Shortcuts MCP` | `Tools/Apple Shortcuts` | 0.88 |

## Out-of-order date sections

- `Entities/Courses/AI-Architect-Certification.md`
  - 2026-04-07 appears after 2026-03-26 (should be reverse-chronological)
- `Entities/Courses/Agentic-Development-Bootcamp.md`
  - 2026-04-07 appears after 2026-02-15 (should be reverse-chronological)
  - 2026-04-10 appears after 2026-04-07 (should be reverse-chronological)
- `Entities/Courses/Data-Preprocessing.md`
  - 2026-04-14 appears after 2026-04-10 (should be reverse-chronological)
  - 2026-04-09 appears after 2026-03-25 (should be reverse-chronological)
- `Entities/Organizations/Anthropic.md`
  - 2026-04-02 appears after 2025-12-02 (should be reverse-chronological)
  - 2026-04-08 appears after 2026-02-19 (should be reverse-chronological)
- `Entities/Organizations/Boeing.md`
  - 2026-03-27 appears after 2026-03-11 (should be reverse-chronological)
- `Entities/Organizations/Cornerstone.md`
  - 2026-04-10 appears after 2026-03-24 (should be reverse-chronological)
- `Entities/Organizations/Deloitte.md`
  - 2026-03-23 appears after 2022-07-01 (should be reverse-chronological)
- `Entities/Organizations/Newman-University.md`
  - 2026-03-31 appears after 2026-01-06 (should be reverse-chronological)
- `Entities/Organizations/Obviant.md`
  - 2026-03-26 appears after 2025-12-19 (should be reverse-chronological)
  - 2026-04-09 appears after 2026-03-26 (should be reverse-chronological)
- `Entities/Organizations/OpenAI.md`
  - 2026-02-18 appears after 2025-12-02 (should be reverse-chronological)
- `Entities/Organizations/Royal-Caribbean.md`
  - 2026-02-28 appears after 2026-02-25 (should be reverse-chronological)
- `Entities/Organizations/Textron-Aviation.md`
  - 2026-03-27 appears after 2026-03-11 (should be reverse-chronological)
- `Entities/Organizations/Tiber-Solutions.md`
  - 2026-04-03 appears after 2025-11-12 (should be reverse-chronological)
  - 2026-04-10 appears after 2026-02-18 (should be reverse-chronological)
- `Entities/Organizations/Wichita-Startup-Supper-Club.md`
  - 2026-04-07 appears after 2026-02-15 (should be reverse-chronological)
- `Entities/Organizations/Zapier.md`
  - 2026-02-27 appears after 2026-01-09 (should be reverse-chronological)
- `Entities/People/Bryan-Lane.md`
  - 2026-03-23 appears after 2022-06-28 (should be reverse-chronological)
  - 2026-03-13 appears after 2025-06-20 (should be reverse-chronological)
- `Entities/People/Chris-Wyant.md`
  - 2026-04-10 appears after 2026-04-07 (should be reverse-chronological)
- `Entities/People/DJ.md`
  - 2026-04-08 appears after 2026-03-06 (should be reverse-chronological)
- `Entities/People/David-Cochran.md`
  - 2026-03-06 appears after 2025-06-20 (should be reverse-chronological)
  - 2026-04-08 appears after 2026-02-21 (should be reverse-chronological)
- `Entities/People/Ellie-Person.md`
  - 2026-04-03 appears after 2026-03-12 (should be reverse-chronological)

## Broken relationship links

- `Entities/People/David-Cochran.md`
  - [Marshall](../Projects/Marshall.md)

## Filename / canonical-slug mismatches

- `Entities/Tools/Firecrawl.md` — Firecrawl.md (expected firecrawl.md from canonical 'firecrawl')
- `Entities/Tools/OpenCode.md` — OpenCode.md (expected opencode.md from canonical 'opencode')

## Suggested fixes (for Unit 3.2 / 3.3)

- **Timeline dedup + sort:** post-process entity pages to (a) dedupe exact-match bullets within a date section, (b) collapse high-similarity near-duplicates, (c) sort date sections descending.
- **Alias resolution:** merge near-duplicate canonical names (see table above); add the losing spelling as an alias on the winner and update extraction prompt to prefer canonical form.
- **Broken links:** either create the missing target entities or strip the relationship line. Broken links compound: `write_entity_page` appends new links without ever retiring stale ones.
