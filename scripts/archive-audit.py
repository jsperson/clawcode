#!/usr/bin/env python3
"""Archive audit — classify every Projects/*/ folder by recency + activity signals.

Produces a report categorizing each project folder:
  - active      — touched in last 30 days, or current initiative per conversations
  - dormant     — no edits in 30-90 days, unclear status
  - ready       — not touched in 90+ days, looks finished or abandoned
  - unknown     — folder exists but has no README or explanatory content

Pure read-only. Writes report to docs/audits/2026-04-archive-audit.md.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
PROJECTS_DIR = VAULT / "Projects"
ARCHIVE_DIR = VAULT / "Archive"
REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_DIR / "docs/audits/2026-04-archive-audit.md"

TZ = ZoneInfo("America/Chicago")
ACTIVE_DAYS = 30
DORMANT_DAYS = 90


def most_recent_mtime(folder: Path) -> datetime:
    """Return the newest mtime across all files in the folder (recursive)."""
    newest = folder.stat().st_mtime
    for p in folder.rglob("*"):
        try:
            if p.is_file():
                newest = max(newest, p.stat().st_mtime)
        except OSError:
            continue
    return datetime.fromtimestamp(newest, tz=TZ)


def count_files(folder: Path) -> tuple[int, int]:
    """Return (md_file_count, total_file_count)."""
    md = 0
    total = 0
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        total += 1
        if p.suffix.lower() == ".md":
            md += 1
    return md, total


def first_paragraph(folder: Path) -> str:
    """Read the first meaningful paragraph from README.md or any top-level .md."""
    candidates = [folder / "README.md"]
    candidates.extend(sorted(folder.glob("*.md")))
    for c in candidates:
        if not c.exists():
            continue
        try:
            text = c.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        # Strip frontmatter
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                text = text[end + 5 :]
        # Strip leading # heading lines
        lines = [l for l in text.split("\n") if l.strip() and not l.strip().startswith("#")]
        if lines:
            # Return first 200 chars of the first non-heading line
            return lines[0].strip()[:200]
    return ""


def classify(folder: Path, now: datetime) -> dict:
    mtime = most_recent_mtime(folder)
    age_days = (now - mtime).days
    md_count, total_count = count_files(folder)
    has_readme = (folder / "README.md").exists()
    summary = first_paragraph(folder)

    if md_count == 0 and total_count == 0:
        status = "empty"
    elif md_count == 0:
        status = "unknown"
    elif age_days <= ACTIVE_DAYS:
        status = "active"
    elif age_days <= DORMANT_DAYS:
        status = "dormant"
    else:
        status = "ready"

    return {
        "name": folder.name,
        "path": str(folder.relative_to(VAULT)),
        "mtime": mtime.strftime("%Y-%m-%d"),
        "age_days": age_days,
        "md_count": md_count,
        "total_count": total_count,
        "has_readme": has_readme,
        "summary": summary,
        "status": status,
    }


def build_report(findings: list[dict], archived: list[str]) -> str:
    by_status: dict[str, list[dict]] = {}
    for f in findings:
        by_status.setdefault(f["status"], []).append(f)

    status_order = ["active", "dormant", "ready", "unknown", "empty"]

    lines = []
    lines.append("# Archive Audit — 2026-04")
    lines.append("")
    lines.append(
        f"Scans `Projects/*/` in the vault. Classifies by most-recent file "
        f"mtime: **active** (≤{ACTIVE_DAYS}d), **dormant** ({ACTIVE_DAYS+1}–"
        f"{DORMANT_DAYS}d), **ready** (>{DORMANT_DAYS}d), **unknown** "
        f"(no markdown), **empty** (no files)."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Project folders scanned:** {len(findings)}")
    for s in status_order:
        count = len(by_status.get(s, []))
        lines.append(f"- **{s}:** {count}")
    lines.append(f"- **Already in Archive/:** {len(archived)} folders")
    lines.append("")

    for s in status_order:
        bucket = by_status.get(s, [])
        if not bucket:
            continue
        lines.append(f"## {s.capitalize()} ({len(bucket)})")
        lines.append("")
        if s == "active":
            lines.append("_Keep these — touched in the last 30 days._")
        elif s == "dormant":
            lines.append("_Review these — stalled but may still be relevant._")
        elif s == "ready":
            lines.append("_Candidates for `Archive/` — no activity in 90+ days._")
        elif s == "unknown":
            lines.append("_No markdown found — investigate what these folders hold._")
        elif s == "empty":
            lines.append("_Empty folders — safe to delete._")
        lines.append("")
        lines.append("| Folder | Last touched | Age (days) | Files | Summary |")
        lines.append("|---|---|---|---|---|")
        for f in sorted(bucket, key=lambda x: x["age_days"]):
            summary = f["summary"].replace("|", "\\|") or "_(no summary)_"
            lines.append(
                f"| `{f['name']}` | {f['mtime']} | {f['age_days']} | "
                f"{f['md_count']}md/{f['total_count']} | {summary} |"
            )
        lines.append("")

    if archived:
        lines.append("## Already in Archive/")
        lines.append("")
        for name in archived:
            lines.append(f"- `{name}`")
        lines.append("")

    lines.append("## Recommended actions")
    lines.append("")
    ready = by_status.get("ready", [])
    if ready:
        lines.append(
            f"- **Move to `Archive/`:** {len(ready)} ready folders. Verify "
            "each one has no loose ends before moving."
        )
        for f in ready[:10]:
            lines.append(f"  - `{f['path']}` (last touched {f['mtime']})")
    dormant = by_status.get("dormant", [])
    if dormant:
        lines.append(
            f"- **Revisit:** {len(dormant)} dormant folders — decide active "
            "or archive."
        )
    unknown = by_status.get("unknown", [])
    if unknown:
        lines.append(f"- **Investigate:** {len(unknown)} folders with no markdown.")
    empty = by_status.get("empty", [])
    if empty:
        lines.append(f"- **Delete:** {len(empty)} empty folders.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    if not PROJECTS_DIR.exists():
        print(f"No Projects dir at {PROJECTS_DIR}")
        return

    now = datetime.now(TZ)
    project_folders = [p for p in sorted(PROJECTS_DIR.iterdir()) if p.is_dir()]
    findings = [classify(p, now) for p in project_folders]

    archived = []
    if ARCHIVE_DIR.exists():
        archived = [p.name for p in sorted(ARCHIVE_DIR.iterdir()) if p.is_dir()]

    report = build_report(findings, archived)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(f"Wrote {args.output.relative_to(REPO_DIR)}")

    counts = {s: 0 for s in ["active", "dormant", "ready", "unknown", "empty"]}
    for f in findings:
        counts[f["status"]] += 1
    parts = [f"{k}={v}" for k, v in counts.items()]
    print(f"{len(findings)} project folders  " + "  ".join(parts))


if __name__ == "__main__":
    main()
