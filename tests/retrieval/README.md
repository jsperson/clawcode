# Retrieval Benchmark

A small curated query suite that measures whether QMD finds the right files
for real questions Scott asks. Runs before and after memory/entity changes
so we can tell when quality moves.

## Run

```bash
cd ~/source/clawcode    # or ~/clawcode — the script auto-locates qmd
python tests/retrieval/run_benchmark.py                        # print scorecard
python tests/retrieval/run_benchmark.py --baseline             # save as baseline
python tests/retrieval/run_benchmark.py --compare tests/retrieval/scorecards/baseline.json
```

Scorecards land under `tests/retrieval/scorecards/` (timestamped). The
`--baseline` flag also writes `scorecards/baseline.json` for future diffs.

## Query file

`benchmark.yaml` holds the queries. Each one has:

```yaml
- id: unique_stable_id
  query: "the question you'd actually type"
  expected_any:
    - "substring/match/against/result/path"
    - "alternative/acceptable/path"
  category: entity | project | decision | cross_ref | alias | skill | memory | infra
```

A query "hits" if any expected substring appears in the top-5 results from
`qmd search` (BM25), `qmd vsearch` (vector), or `qmd query` (hybrid +
rerank). Scoring is precision@5 per mode.

## Adding queries

When you notice a question you expected to find a thing, write a query.
Good candidates:

- Something you just searched for that didn't work → add it, fix the
  underlying cause, re-run to verify
- A decision buried in a daily log that should be easy to recall
- An entity you conflate (Marshal vs Marshall)

Keep the query phrasing natural — the point is to measure real-use
retrieval, not word-for-word match against canonical entity names.

## Interpreting scores

- **BM25 (`search`)** — best for literal keyword matches; weakest on
  synonyms and reworded questions
- **Vector (`vsearch`)** — best for meaning-based questions; weakest on
  specific terms the corpus doesn't use verbatim
- **Hybrid (`query`)** — reranks both, should be best overall

If hybrid loses to either specialized mode on a category, the reranker
may be miscalibrated for that category — worth flagging.

## Not a CI gate

Results depend on corpus state and QMD index freshness. Run manually
before/after changes; don't wire into automated test suites.
