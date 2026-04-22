#!/usr/bin/env python3
"""Run the retrieval benchmark and emit a scorecard.

Reads tests/retrieval/benchmark.yaml, runs each query through qmd search
(BM25), qmd vsearch (vector), and qmd query (reranked hybrid), scores
precision@5, and writes a timestamped scorecard.

Usage:
    python tests/retrieval/run_benchmark.py               # run, print scorecard
    python tests/retrieval/run_benchmark.py --baseline    # also save as baseline
    python tests/retrieval/run_benchmark.py --compare F   # diff against baseline F
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

TZ = ZoneInfo("America/Chicago")
BENCHMARK_DIR = Path(__file__).resolve().parent
REPO_DIR = BENCHMARK_DIR.parent.parent
SCORECARDS_DIR = BENCHMARK_DIR / "scorecards"

# Each result block starts with a qmd:// URI line.
QMD_URI_RE = re.compile(r"^qmd://(?P<path>[^\s:]+)", re.MULTILINE)

MODES = ["search", "vsearch", "query"]
TOP_N = 5


def run_qmd(mode: str, query: str) -> list[str]:
    """Run qmd <mode> <query> and return the top matching paths."""
    try:
        result = subprocess.run(
            ["qmd", mode, query],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return []
    if result.returncode != 0:
        return []
    paths = QMD_URI_RE.findall(result.stdout)
    return paths[:TOP_N]


def score_query(expected_any: list[str], results: list[str]) -> dict:
    """Return hit info: whether any expected pattern matched, and rank of first hit."""
    normalized_results = [r.lower() for r in results]
    for rank, r in enumerate(normalized_results, start=1):
        for expected in expected_any:
            if expected.lower() in r:
                return {"hit": True, "rank": rank, "matched_on": expected}
    return {"hit": False, "rank": None, "matched_on": None}


def run_benchmark() -> dict:
    bench = yaml.safe_load((BENCHMARK_DIR / "benchmark.yaml").read_text())
    queries = bench["queries"]

    scorecard = {
        "generated": datetime.now(TZ).isoformat(timespec="seconds"),
        "query_count": len(queries),
        "modes": MODES,
        "top_n": TOP_N,
        "results": [],
    }

    for q in queries:
        row = {
            "id": q["id"],
            "query": q["query"],
            "category": q.get("category", "uncategorized"),
            "expected_any": q["expected_any"],
            "modes": {},
        }
        for mode in MODES:
            results = run_qmd(mode, q["query"])
            score = score_query(q["expected_any"], results)
            row["modes"][mode] = {
                **score,
                "top_paths": results,
            }
        scorecard["results"].append(row)

    # Aggregate
    totals = {mode: {"hits": 0, "total": len(queries)} for mode in MODES}
    for row in scorecard["results"]:
        for mode in MODES:
            if row["modes"][mode]["hit"]:
                totals[mode]["hits"] += 1
    scorecard["aggregate"] = {
        mode: {
            "hits": t["hits"],
            "total": t["total"],
            "precision_at_5": round(t["hits"] / t["total"], 3) if t["total"] else 0,
        }
        for mode, t in totals.items()
    }
    return scorecard


def print_scorecard(s: dict) -> None:
    print(f"Benchmark run {s['generated']}")
    print(f"  queries: {s['query_count']}   top-N: {s['top_n']}")
    print()
    for row in s["results"]:
        marks = []
        for mode in MODES:
            r = row["modes"][mode]
            mark = f"✓@{r['rank']}" if r["hit"] else "✗"
            marks.append(f"{mode}:{mark}")
        print(f"  [{row['category']:<10}] {row['id']:<32} {'  '.join(marks)}")
    print()
    print("Aggregate precision@{}".format(TOP_N))
    for mode, agg in s["aggregate"].items():
        print(f"  {mode:<8} {agg['hits']}/{agg['total']}  ({agg['precision_at_5']:.1%})")


def write_scorecard(s: dict, filename: str) -> Path:
    SCORECARDS_DIR.mkdir(exist_ok=True)
    path = SCORECARDS_DIR / filename
    path.write_text(json.dumps(s, indent=2))
    return path


def diff_against_baseline(current: dict, baseline_path: Path) -> None:
    baseline = json.loads(baseline_path.read_text())
    print(f"\nDiff vs {baseline_path.name}:")
    changes = []
    for row in current["results"]:
        b_row = next((r for r in baseline["results"] if r["id"] == row["id"]), None)
        if not b_row:
            continue
        for mode in MODES:
            c_hit = row["modes"][mode]["hit"]
            b_hit = b_row["modes"][mode]["hit"]
            if c_hit != b_hit:
                direction = "↑" if c_hit else "↓"
                changes.append(f"  {direction} {row['id']} [{mode}]: {b_hit} → {c_hit}")
    if not changes:
        print("  No changes.")
    else:
        for c in changes:
            print(c)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="Save this run as the baseline")
    ap.add_argument("--compare", help="Path to baseline scorecard to diff against")
    args = ap.parse_args()

    scorecard = run_benchmark()
    print_scorecard(scorecard)

    stamp = datetime.now(TZ).strftime("%Y-%m-%d-%H%M")
    filename = f"{stamp}.json"
    path = write_scorecard(scorecard, filename)
    print(f"\nWrote {path.relative_to(REPO_DIR)}")

    if args.baseline:
        baseline_path = SCORECARDS_DIR / "baseline.json"
        baseline_path.write_text(json.dumps(scorecard, indent=2))
        print(f"Saved as baseline: {baseline_path.relative_to(REPO_DIR)}")

    if args.compare:
        diff_against_baseline(scorecard, Path(args.compare))


if __name__ == "__main__":
    main()
