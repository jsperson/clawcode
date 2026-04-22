#!/usr/bin/env python3
"""Entity normalizer — dedupe and chronologically sort entity timelines.

For each entity page under Entities/**/*.md:
  1. Parse frontmatter + sections
  2. Within each Timeline date section, drop exact-duplicate bullets and
     near-duplicates (SequenceMatcher ratio >= threshold). Keep the longest
     variant — it almost always contains strictly more information.
  3. Sort date sections reverse-chronologically.
  4. Deduplicate relationship links by target filename.
  5. Rewrite the file only if changes are needed.

Defaults to --dry-run. Pass --write to actually modify files.

Safe to re-run. Designed to be idempotent.

Usage:
    scripts/entity-normalize.py                    # dry run report
    scripts/entity-normalize.py --write            # apply fixes
    scripts/entity-normalize.py --path Entities/Projects/ClawCode.md --write
"""

from __future__ import annotations

import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

VAULT_PATH = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
ENTITIES_DIR = VAULT_PATH / "Entities"

DATE_HEADER_RE = re.compile(r"^### (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
BULLET_RE = re.compile(r"^-\s+(.+)$")
RELATIONSHIP_LINK_RE = re.compile(r"^-\s*\[([^\]]+)\]\(([^)]+)\)\s*(?:—.*)?$")

NEAR_DUP_THRESHOLD = 0.85


def parse_page(text: str) -> dict:
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not fm_match:
        return {"frontmatter": "", "body": text, "has_fm": False}
    return {
        "frontmatter": fm_match.group(1),
        "body": fm_match.group(2),
        "has_fm": True,
    }


def extract_section(body: str, header: str) -> tuple[int, int, str]:
    """Return (start, end, content) for a ## section, or (-1, -1, '') if absent."""
    m = re.search(rf"^## {re.escape(header)}\s*$", body, re.MULTILINE)
    if not m:
        return -1, -1, ""
    start = m.end()
    nxt = re.search(r"^## ", body[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(body)
    return m.start(), end, body[start:end].strip()


def split_timeline(timeline: str) -> list[tuple[str, list[str]]]:
    if not timeline:
        return []
    matches = list(DATE_HEADER_RE.finditer(timeline))
    sections = []
    for i, m in enumerate(matches):
        date = m.group(1)
        s, e = m.end(), (matches[i + 1].start() if i + 1 < len(matches) else len(timeline))
        bullets = []
        for line in timeline[s:e].split("\n"):
            bm = BULLET_RE.match(line.strip())
            if bm:
                bullets.append(bm.group(1).strip())
        sections.append((date, bullets))
    return sections


def dedupe_bullets(bullets: list[str]) -> tuple[list[str], int, int]:
    """Return (kept, exact_dropped, near_dropped). Keeps the longest variant."""
    exact_dropped = 0
    seen_exact = {}
    unique = []
    for b in bullets:
        key = b.lower().strip()
        if key in seen_exact:
            exact_dropped += 1
            # Prefer longer version if duplicate
            idx = seen_exact[key]
            if len(b) > len(unique[idx]):
                unique[idx] = b
        else:
            seen_exact[key] = len(unique)
            unique.append(b)

    # Near-dup pass: for each bullet, drop it if a longer bullet already kept
    # has ratio >= threshold.
    near_dropped = 0
    kept: list[str] = []
    for b in unique:
        drop = False
        for i, k in enumerate(kept):
            ratio = SequenceMatcher(None, b.lower(), k.lower()).ratio()
            if ratio >= NEAR_DUP_THRESHOLD:
                # Keep the longer one
                if len(b) > len(k):
                    kept[i] = b
                drop = True
                near_dropped += 1
                break
        if not drop:
            kept.append(b)

    return kept, exact_dropped, near_dropped


def dedupe_relationships(rel_text: str) -> tuple[str, int]:
    """Dedupe relationship lines by target path; return (new_text, dropped_count)."""
    if not rel_text or rel_text.strip() == "*None yet.*":
        return rel_text, 0

    seen_targets = set()
    kept_lines = []
    dropped = 0
    for line in rel_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        m = RELATIONSHIP_LINK_RE.match(stripped)
        if not m:
            kept_lines.append(line)
            continue
        target = m.group(2).lower()
        if target in seen_targets:
            dropped += 1
            continue
        seen_targets.add(target)
        kept_lines.append(line)

    return "\n".join(kept_lines), dropped


def rebuild_timeline(sections: list[tuple[str, list[str]]]) -> str:
    """Build timeline text from sorted sections (most recent first)."""
    parts = []
    for date, bullets in sections:
        parts.append(f"### {date}")
        for b in bullets:
            parts.append(f"- {b}")
        parts.append("")  # blank line between date sections
    return "\n".join(parts).rstrip()


def normalize_page(text: str) -> tuple[str, dict]:
    """Return (new_text, stats). new_text is identical if no changes."""
    stats = {
        "exact_bullets_dropped": 0,
        "near_bullets_dropped": 0,
        "dates_resorted": 0,
        "relationships_dropped": 0,
        "changed": False,
    }

    parsed = parse_page(text)
    if not parsed["has_fm"]:
        return text, stats
    body = parsed["body"]

    # Extract Timeline section
    tl_start, tl_end, tl_text = extract_section(body, "Timeline")
    new_body = body
    if tl_start >= 0:
        sections = split_timeline(tl_text)
        cleaned = []
        for date, bullets in sections:
            kept, ex, nr = dedupe_bullets(bullets)
            stats["exact_bullets_dropped"] += ex
            stats["near_bullets_dropped"] += nr
            cleaned.append((date, kept))

        # Sort reverse-chron (stable on dates)
        sorted_sections = sorted(cleaned, key=lambda x: x[0], reverse=True)
        if [d for d, _ in sorted_sections] != [d for d, _ in sections]:
            stats["dates_resorted"] = 1

        new_timeline = rebuild_timeline(sorted_sections)
        new_body = body[:tl_start] + f"## Timeline\n\n{new_timeline}\n" + body[tl_end:]

    # Relationships dedup
    rel_start, rel_end, rel_text = extract_section(new_body, "Relationships")
    if rel_start >= 0:
        cleaned_rel, dropped = dedupe_relationships(rel_text)
        stats["relationships_dropped"] = dropped
        if dropped:
            new_body = (
                new_body[:rel_start]
                + f"## Relationships\n\n{cleaned_rel}\n\n"
                + new_body[rel_end:]
            )

    new_text = f"---\n{parsed['frontmatter']}\n---\n{new_body}"
    # Normalize trailing whitespace
    new_text = new_text.rstrip() + "\n"

    if new_text != text:
        stats["changed"] = True

    return new_text, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Actually write changes")
    ap.add_argument("--path", type=Path, help="Single file to normalize")
    args = ap.parse_args()

    if args.path:
        paths = [args.path if args.path.is_absolute() else VAULT_PATH / args.path]
    else:
        paths = sorted(ENTITIES_DIR.glob("*/*.md"))

    totals = {
        "files_scanned": 0,
        "files_changed": 0,
        "exact_bullets_dropped": 0,
        "near_bullets_dropped": 0,
        "dates_resorted": 0,
        "relationships_dropped": 0,
    }
    changed_files = []

    for p in paths:
        totals["files_scanned"] += 1
        text = p.read_text()
        new_text, stats = normalize_page(text)
        if stats["changed"]:
            totals["files_changed"] += 1
            changed_files.append((p, stats))
            for k in ("exact_bullets_dropped", "near_bullets_dropped",
                      "dates_resorted", "relationships_dropped"):
                totals[k] += stats[k]
            if args.write:
                p.write_text(new_text)

    mode = "WRITE" if args.write else "DRY RUN"
    print(f"[{mode}]")
    print(f"  Files scanned: {totals['files_scanned']}")
    print(f"  Files {'changed' if args.write else 'would change'}: {totals['files_changed']}")
    print(f"  Exact-duplicate bullets dropped: {totals['exact_bullets_dropped']}")
    print(f"  Near-duplicate bullets dropped:  {totals['near_bullets_dropped']}")
    print(f"  Entities with dates resorted:    {totals['dates_resorted']}")
    print(f"  Relationship duplicates dropped: {totals['relationships_dropped']}")
    print()
    print("Top changes:")
    top = sorted(
        changed_files,
        key=lambda x: (
            x[1]["exact_bullets_dropped"] + x[1]["near_bullets_dropped"]
        ),
        reverse=True,
    )[:15]
    for p, s in top:
        print(
            f"  {p.relative_to(VAULT_PATH)}  "
            f"-{s['exact_bullets_dropped']} exact  "
            f"-{s['near_bullets_dropped']} near  "
            f"resort={s['dates_resorted']}  "
            f"-{s['relationships_dropped']} rel"
        )


if __name__ == "__main__":
    main()
