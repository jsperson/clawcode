#!/usr/bin/env python3
"""Entity audit — quantify quality issues in the Obsidian entity graph.

Walks Entities/**/*.md and reports:
  - Duplicate timeline bullets within a single date section (exact + near-exact)
  - Out-of-order date sections in Timeline (should be most-recent-first)
  - Near-duplicate canonical names across the whole graph (Marshal vs Marshall)
  - Broken relationship links (targets whose files don't exist)
  - Filename / canonical name slug mismatches

Writes a summary report to docs/audits/2026-04-entity-audit.md (or the path
passed via --output). Read-only — does not touch the vault.

Usage:
    scripts/entity-audit.py
    scripts/entity-audit.py --output path/to/report.md
    scripts/entity-audit.py --json            # also dump raw findings JSON
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

VAULT_PATH = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
ENTITIES_DIR = VAULT_PATH / "Entities"
REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_DIR / "docs/audits/2026-04-entity-audit.md"

DATE_HEADER_RE = re.compile(r"^### (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
BULLET_RE = re.compile(r"^-\s+(.*)$")
RELATIONSHIP_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

NEAR_DUP_THRESHOLD = 0.85  # SequenceMatcher ratio
NEAR_DUP_NAME_THRESHOLD = 0.88


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name)
    return re.sub(r"\s+", "-", slug.strip())


def parse_sections(text: str) -> dict:
    """Split entity body into frontmatter, compiled_truth, relationships, timeline."""
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    body = fm_match.group(2) if fm_match else text

    def grab(header: str) -> str:
        m = re.search(rf"## {header}\n\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
        return m.group(1).strip() if m else ""

    return {
        "frontmatter_raw": fm_match.group(1) if fm_match else "",
        "compiled_truth": grab("Compiled Truth"),
        "relationships": grab("Relationships"),
        "timeline": grab("Timeline"),
    }


def split_timeline_by_date(timeline: str) -> list[tuple[str, list[str]]]:
    """Return [(date_str, [bullet_text, ...]), ...] in document order."""
    if not timeline:
        return []

    sections = []
    matches = list(DATE_HEADER_RE.finditer(timeline))
    for i, m in enumerate(matches):
        date = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(timeline)
        body = timeline[start:end].strip()
        bullets = []
        for line in body.split("\n"):
            bm = BULLET_RE.match(line.strip())
            if bm:
                bullets.append(bm.group(1).strip())
        sections.append((date, bullets))
    return sections


def count_dup_bullets(bullets: list[str]) -> tuple[int, int, list[tuple[str, str]]]:
    """Return (exact_dup_count, near_dup_count, sample_pairs)."""
    exact = 0
    seen = {}
    for b in bullets:
        key = b.lower().strip()
        if key in seen:
            exact += 1
        else:
            seen[key] = b

    near = 0
    samples = []
    uniq = list(seen.values())
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            ratio = SequenceMatcher(None, uniq[i].lower(), uniq[j].lower()).ratio()
            if ratio >= NEAR_DUP_THRESHOLD:
                near += 1
                if len(samples) < 2:
                    samples.append((uniq[i], uniq[j]))
    return exact, near, samples


def dates_out_of_order(sections: list[tuple[str, list[str]]]) -> list[str]:
    """Return list of dates that appear after a later date (violating reverse-chron)."""
    violations = []
    prev = None
    for date, _ in sections:
        if prev is not None and date > prev:
            violations.append(f"{date} appears after {prev} (should be reverse-chronological)")
        prev = date
    return violations


def find_near_duplicate_names(all_entities: list[dict]) -> list[tuple[str, str, float]]:
    """Compare canonical names across all entities, return near-dup triples."""
    dups = []
    for i in range(len(all_entities)):
        for j in range(i + 1, len(all_entities)):
            a, b = all_entities[i], all_entities[j]
            if a["canonical"].lower() == b["canonical"].lower():
                continue
            ratio = SequenceMatcher(
                None, a["canonical"].lower(), b["canonical"].lower()
            ).ratio()
            if ratio >= NEAR_DUP_NAME_THRESHOLD:
                label_a = f"{a['type']}/{a['canonical']}"
                label_b = f"{b['type']}/{b['canonical']}"
                dups.append((label_a, label_b, ratio))
    return sorted(dups, key=lambda t: -t[2])


def check_relationship_links(rel_text: str, base_path: Path) -> list[str]:
    """Return list of broken link targets (relative paths that don't exist)."""
    broken = []
    for name, target in RELATIONSHIP_LINK_RE.findall(rel_text):
        if target.startswith(("http://", "https://")):
            continue
        resolved = (base_path.parent / target).resolve()
        if not resolved.exists():
            broken.append(f"[{name}]({target})")
    return broken


def audit_entity(path: Path) -> dict:
    text = path.read_text()
    sections = parse_sections(text)
    timeline_sections = split_timeline_by_date(sections["timeline"])

    # Per-date duplicate stats
    per_date_dups = []
    total_exact = 0
    total_near = 0
    for date, bullets in timeline_sections:
        exact, near, samples = count_dup_bullets(bullets)
        if exact or near:
            per_date_dups.append(
                {
                    "date": date,
                    "bullet_count": len(bullets),
                    "exact_dups": exact,
                    "near_dups": near,
                    "samples": samples,
                }
            )
            total_exact += exact
            total_near += near

    order_issues = dates_out_of_order(timeline_sections)
    broken_links = check_relationship_links(sections["relationships"], path)

    # Infer canonical and type from path + frontmatter
    type_dir = path.parent.name
    canonical_from_fm = None
    m = re.search(r"^canonical_name:\s*(.+)$", sections["frontmatter_raw"], re.MULTILINE)
    if m:
        canonical_from_fm = m.group(1).strip().strip("'\"")
    canonical = canonical_from_fm or path.stem.replace("-", " ")

    expected_slug = slugify(canonical)
    filename_mismatch = None
    if expected_slug != path.stem:
        filename_mismatch = f"{path.stem}.md (expected {expected_slug}.md from canonical {canonical!r})"

    return {
        "path": str(path.relative_to(VAULT_PATH)),
        "type": type_dir,
        "canonical": canonical,
        "date_sections": len(timeline_sections),
        "total_bullets": sum(len(b) for _, b in timeline_sections),
        "exact_dup_bullets": total_exact,
        "near_dup_bullets": total_near,
        "per_date_dups": per_date_dups,
        "out_of_order_dates": order_issues,
        "broken_relationship_links": broken_links,
        "filename_mismatch": filename_mismatch,
    }


def build_report(findings: list[dict], name_dups: list[tuple[str, str, float]]) -> str:
    total_entities = len(findings)
    with_exact = [f for f in findings if f["exact_dup_bullets"]]
    with_near = [f for f in findings if f["near_dup_bullets"]]
    with_order = [f for f in findings if f["out_of_order_dates"]]
    with_broken = [f for f in findings if f["broken_relationship_links"]]
    with_fname = [f for f in findings if f["filename_mismatch"]]

    total_exact = sum(f["exact_dup_bullets"] for f in findings)
    total_near = sum(f["near_dup_bullets"] for f in findings)
    total_bullets = sum(f["total_bullets"] for f in findings)

    top_dup = sorted(
        findings,
        key=lambda f: (f["exact_dup_bullets"] + f["near_dup_bullets"]),
        reverse=True,
    )[:10]

    lines = []
    lines.append("# Entity Graph Audit — 2026-04")
    lines.append("")
    lines.append("Read-only audit of `Entities/**/*.md` to quantify quality issues")
    lines.append("before patching `scripts/entity-graph.py`.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Entities scanned:** {total_entities}")
    lines.append(f"- **Total timeline bullets:** {total_bullets}")
    lines.append(
        f"- **Exact-duplicate bullets (within a date section):** {total_exact} "
        f"across {len(with_exact)} entities"
    )
    lines.append(
        f"- **Near-duplicate bullets (ratio ≥ {NEAR_DUP_THRESHOLD}):** {total_near} "
        f"across {len(with_near)} entities"
    )
    lines.append(f"- **Entities with out-of-order date sections:** {len(with_order)}")
    lines.append(
        f"- **Entities with broken relationship links:** {len(with_broken)}"
    )
    lines.append(f"- **Filename / canonical-slug mismatches:** {len(with_fname)}")
    lines.append(
        f"- **Near-duplicate canonical names (ratio ≥ {NEAR_DUP_NAME_THRESHOLD}):** "
        f"{len(name_dups)}"
    )
    lines.append("")

    lines.append("## Top offenders — timeline duplication")
    lines.append("")
    lines.append("| Entity | Dates | Bullets | Exact dups | Near dups |")
    lines.append("|---|---|---|---|---|")
    for f in top_dup:
        if f["exact_dup_bullets"] + f["near_dup_bullets"] == 0:
            continue
        lines.append(
            f"| `{f['path']}` | {f['date_sections']} | {f['total_bullets']} | "
            f"{f['exact_dup_bullets']} | {f['near_dup_bullets']} |"
        )
    lines.append("")

    # Sample duplicate pairs from the worst offender
    if top_dup and top_dup[0]["per_date_dups"]:
        worst = top_dup[0]
        lines.append(f"### Sample near-duplicate pairs from `{worst['path']}`")
        lines.append("")
        for d in worst["per_date_dups"][:2]:
            for a, b in d["samples"][:2]:
                lines.append(f"- **{d['date']}**")
                lines.append(f"  - `{a}`")
                lines.append(f"  - `{b}`")
        lines.append("")

    if name_dups:
        lines.append("## Near-duplicate canonical names")
        lines.append("")
        lines.append("| Entity A | Entity B | Similarity |")
        lines.append("|---|---|---|")
        for a, b, r in name_dups[:20]:
            lines.append(f"| `{a}` | `{b}` | {r:.2f} |")
        lines.append("")

    if with_order:
        lines.append("## Out-of-order date sections")
        lines.append("")
        for f in with_order[:20]:
            lines.append(f"- `{f['path']}`")
            for v in f["out_of_order_dates"][:3]:
                lines.append(f"  - {v}")
        lines.append("")

    if with_broken:
        lines.append("## Broken relationship links")
        lines.append("")
        for f in with_broken[:20]:
            lines.append(f"- `{f['path']}`")
            for b in f["broken_relationship_links"][:5]:
                lines.append(f"  - {b}")
        lines.append("")

    if with_fname:
        lines.append("## Filename / canonical-slug mismatches")
        lines.append("")
        for f in with_fname[:20]:
            lines.append(f"- `{f['path']}` — {f['filename_mismatch']}")
        lines.append("")

    lines.append("## Suggested fixes (for Unit 3.2 / 3.3)")
    lines.append("")
    lines.append(
        "- **Timeline dedup + sort:** post-process entity pages to (a) dedupe "
        "exact-match bullets within a date section, (b) collapse high-similarity "
        "near-duplicates, (c) sort date sections descending."
    )
    lines.append(
        "- **Alias resolution:** merge near-duplicate canonical names (see table "
        "above); add the losing spelling as an alias on the winner and update "
        "extraction prompt to prefer canonical form."
    )
    lines.append(
        "- **Broken links:** either create the missing target entities or strip "
        "the relationship line. Broken links compound: `write_entity_page` "
        "appends new links without ever retiring stale ones."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--json", action="store_true", help="Also write raw JSON findings")
    args = ap.parse_args()

    paths = sorted(ENTITIES_DIR.glob("*/*.md"))
    findings = [audit_entity(p) for p in paths]

    entities_for_dup_check = [
        {"canonical": f["canonical"], "type": f["type"]} for f in findings
    ]
    name_dups = find_near_duplicate_names(entities_for_dup_check)

    report = build_report(findings, name_dups)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(f"Wrote {args.output.relative_to(REPO_DIR)}")

    if args.json:
        json_path = args.output.with_suffix(".json")
        json_path.write_text(
            json.dumps(
                {"findings": findings, "name_duplicates": name_dups},
                indent=2,
                default=str,
            )
        )
        print(f"Wrote {json_path.relative_to(REPO_DIR)}")

    # Short console summary
    total_exact = sum(f["exact_dup_bullets"] for f in findings)
    total_near = sum(f["near_dup_bullets"] for f in findings)
    print(
        f"{len(findings)} entities  "
        f"{total_exact} exact dup bullets  "
        f"{total_near} near dups  "
        f"{len(name_dups)} near-duplicate canonical names"
    )


if __name__ == "__main__":
    main()
