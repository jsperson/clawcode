# Entity Graph Audit — 2026-04

Read-only audit of `Entities/**/*.md` to quantify quality issues
before patching `scripts/entity-graph.py`.

## Summary

- **Entities scanned:** 308
- **Total timeline bullets:** 1993
- **Exact-duplicate bullets (within a date section):** 0 across 0 entities
- **Near-duplicate bullets (ratio ≥ 0.85):** 1 across 1 entities
- **Entities with out-of-order date sections:** 0
- **Entities with broken relationship links:** 0
- **Filename / canonical-slug mismatches:** 0
- **Near-duplicate canonical names (ratio ≥ 0.88):** 1

## Top offenders — timeline duplication

| Entity | Dates | Bullets | Exact dups | Near dups |
|---|---|---|---|---|
| `Entities/Organizations/OpenAI.md` | 3 | 4 | 0 | 1 |

### Sample near-duplicate pairs from `Entities/Organizations/OpenAI.md`

- **2026-02-18**
  - `Scott researched GPT-5.x model lineup, Plus vs Pro quotas, and Codex limits on 2026-02-18`
  - `Scott researched GPT-5.x model lineup, Plus vs Pro plan quotas, and Codex limits`

## Near-duplicate canonical names

| Entity A | Entity B | Similarity |
|---|---|---|
| `People/Lilly` | `People/Lily` | 0.89 |

## Suggested fixes (for Unit 3.2 / 3.3)

- **Timeline dedup + sort:** post-process entity pages to (a) dedupe exact-match bullets within a date section, (b) collapse high-similarity near-duplicates, (c) sort date sections descending.
- **Alias resolution:** merge near-duplicate canonical names (see table above); add the losing spelling as an alias on the winner and update extraction prompt to prefer canonical form.
- **Broken links:** either create the missing target entities or strip the relationship line. Broken links compound: `write_entity_page` appends new links without ever retiring stale ones.
