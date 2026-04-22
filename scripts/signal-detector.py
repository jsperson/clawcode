#!/usr/bin/env python3
"""Signal detector — surface drift before it causes damage.

Read-only scan that flags:
  - Stale memory topics (>60 days since last modification)
  - Broken entity relationship links
  - Near-duplicate canonical entity names
  - Dormant Projects/ folders (>30 days)
  - Stalled scheduled jobs (no log output in >2x expected cadence)

Writes a signals report to life-agent/signals/YYYY-MM-DD-signals.md.
Does not auto-fix anything — Scott reads, decides, acts.

Usage:
    scripts/signal-detector.py                # today's report
    scripts/signal-detector.py --output PATH  # custom output path
    scripts/signal-detector.py --stdout       # print to stdout, no file
"""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")

DEPLOYED_DIR = Path.home() / "clawcode"
TOPICS_DIR = DEPLOYED_DIR / "memory/topics"
LOGS_DIR = DEPLOYED_DIR / "data/logs"
SCHEDULES_YAML = DEPLOYED_DIR / "config/schedules.yaml"

VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
ENTITIES_DIR = VAULT / "Entities"
PROJECTS_DIR = VAULT / "Projects"

STALE_TOPIC_DAYS = 60
DORMANT_PROJECT_DAYS = 30
NEAR_DUP_NAME_THRESHOLD = 0.88


def detect_stale_topics(now: datetime) -> list[dict]:
    signals = []
    if not TOPICS_DIR.exists():
        return signals
    for p in sorted(TOPICS_DIR.glob("*.md")):
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=TZ)
        age = (now - mtime).days
        if age > STALE_TOPIC_DAYS:
            signals.append(
                {"path": p.name, "last_modified": mtime.strftime("%Y-%m-%d"), "age_days": age}
            )
    return signals


def detect_broken_entity_links() -> list[dict]:
    signals = []
    link_re = re.compile(r"\[([^\]]+)\]\((\.\./[^)]+\.md)\)")
    for p in sorted(ENTITIES_DIR.glob("*/*.md")):
        text = p.read_text()
        for name, target in link_re.findall(text):
            resolved = (p.parent / target).resolve()
            if not resolved.exists():
                signals.append(
                    {
                        "source": str(p.relative_to(VAULT)),
                        "link_name": name,
                        "missing_target": target,
                    }
                )
    return signals


def detect_near_duplicate_entity_names() -> list[dict]:
    signals = []
    entities = []
    for p in sorted(ENTITIES_DIR.glob("*/*.md")):
        entities.append({"type": p.parent.name, "name": p.stem.replace("-", " "), "path": p})
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            a, b = entities[i], entities[j]
            if a["name"].lower() == b["name"].lower():
                continue
            ratio = SequenceMatcher(None, a["name"].lower(), b["name"].lower()).ratio()
            if ratio >= NEAR_DUP_NAME_THRESHOLD:
                signals.append(
                    {
                        "a": f"{a['type']}/{a['name']}",
                        "b": f"{b['type']}/{b['name']}",
                        "similarity": round(ratio, 3),
                    }
                )
    return signals


def detect_dormant_projects(now: datetime) -> list[dict]:
    signals = []
    if not PROJECTS_DIR.exists():
        return signals
    for folder in sorted(PROJECTS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        newest = folder.stat().st_mtime
        for p in folder.rglob("*"):
            try:
                if p.is_file():
                    newest = max(newest, p.stat().st_mtime)
            except OSError:
                continue
        mtime = datetime.fromtimestamp(newest, tz=TZ)
        age = (now - mtime).days
        if age > DORMANT_PROJECT_DAYS:
            signals.append(
                {"name": folder.name, "last_touched": mtime.strftime("%Y-%m-%d"), "age_days": age}
            )
    return signals


# Parse a subset of cron expressions into an expected-cadence bucket in hours.
# We only care about "is this job chronically silent", not exact next-fire time.
CADENCE_HOURS = {
    # minute hour day-of-month month day-of-week
    r"\*/\d+ \* \* \* \*": 1,            # every N minutes → expect ≤1h silence
    r"\d+ \* \* \* \*": 1,                # every hour at N min
    r"\d+ \d+ \* \* \*": 24,              # daily
    r"\d+ \d+ \* \* [0-6]": 24 * 7,       # weekly (specific weekday)
    r"\d+ \d+ \* \* \*/\d+": 24 * 2,      # every N days-ish
    r"\d+ \d+ 1 \* \*": 24 * 30,          # monthly (day 1)
}


def expected_cadence_hours(cron: str) -> int | None:
    cron = cron.strip()
    for pattern, hours in CADENCE_HOURS.items():
        if re.fullmatch(pattern, cron):
            return hours
    # Fallback — weekly specific weekday e.g. "0 3 * * 1"
    if re.fullmatch(r"\d+ \d+ \* \* \d", cron):
        return 24 * 7
    return None


def detect_stalled_schedules(now: datetime) -> list[dict]:
    signals = []
    if not SCHEDULES_YAML.exists() or not LOGS_DIR.exists():
        return signals

    # Inline mini yaml parse rather than pulling in yaml dep. schedules.yaml
    # top-level is `schedules: {name: {cron: "...", enabled: true, ...}}`
    text = SCHEDULES_YAML.read_text()
    # Crude: find each job block — lines like "  <name>:" followed by indented keys
    job_re = re.compile(r"^  ([a-z_][a-z0-9_]*):\s*$", re.MULTILINE)
    jobs = {}
    matches = list(job_re.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        cron_m = re.search(r'^\s+cron:\s*"([^"]+)"', block, re.MULTILINE)
        enabled_m = re.search(r"^\s+enabled:\s*(true|false)", block, re.MULTILINE)
        if not cron_m:
            continue
        jobs[name] = {
            "cron": cron_m.group(1),
            "enabled": enabled_m.group(1) == "true" if enabled_m else True,
        }

    for name, info in jobs.items():
        if not info["enabled"]:
            continue
        cadence = expected_cadence_hours(info["cron"])
        if not cadence:
            continue  # unknown cadence — don't flag
        log = LOGS_DIR / f"schedule-{name}.log"
        if not log.exists():
            signals.append(
                {
                    "job": name,
                    "cron": info["cron"],
                    "issue": "no log file exists",
                    "age_hours": None,
                }
            )
            continue
        mtime = datetime.fromtimestamp(log.stat().st_mtime, tz=TZ)
        age_hours = (now - mtime).total_seconds() / 3600
        threshold = cadence * 2
        if age_hours > threshold:
            signals.append(
                {
                    "job": name,
                    "cron": info["cron"],
                    "last_output": mtime.strftime("%Y-%m-%d %H:%M"),
                    "age_hours": round(age_hours, 1),
                    "expected_within_hours": cadence,
                }
            )
    return signals


def build_report(
    now: datetime,
    stale_topics: list[dict],
    broken_links: list[dict],
    name_dups: list[dict],
    dormant_projects: list[dict],
    stalled_schedules: list[dict],
) -> str:
    total = (
        len(stale_topics)
        + len(broken_links)
        + len(name_dups)
        + len(dormant_projects)
        + len(stalled_schedules)
    )
    lines = [f"# Signals — {now.strftime('%Y-%m-%d %H:%M')}", ""]
    lines.append(f"Total signals: **{total}**")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|---|---|")
    lines.append(f"| Stale memory topics (>{STALE_TOPIC_DAYS}d) | {len(stale_topics)} |")
    lines.append(f"| Broken entity links | {len(broken_links)} |")
    lines.append(f"| Near-duplicate entity names | {len(name_dups)} |")
    lines.append(f"| Dormant Projects/ folders (>{DORMANT_PROJECT_DAYS}d) | {len(dormant_projects)} |")
    lines.append(f"| Stalled scheduled jobs | {len(stalled_schedules)} |")
    lines.append("")

    if stale_topics:
        lines.append("## Stale memory topics")
        lines.append("")
        for s in stale_topics:
            lines.append(f"- `{s['path']}` — last modified {s['last_modified']} ({s['age_days']}d ago)")
        lines.append("")

    if broken_links:
        lines.append("## Broken entity links")
        lines.append("")
        for s in broken_links:
            lines.append(
                f"- `{s['source']}` → `[{s['link_name']}]({s['missing_target']})` — target missing"
            )
        lines.append("")

    if name_dups:
        lines.append("## Near-duplicate entity names")
        lines.append("")
        lines.append("_Flag before they split into phantom duplicates (Marshal/Marshall pattern)._")
        lines.append("")
        for s in name_dups:
            lines.append(f"- `{s['a']}` vs `{s['b']}` (similarity {s['similarity']})")
        lines.append("")

    if dormant_projects:
        lines.append("## Dormant Projects/ folders")
        lines.append("")
        for s in dormant_projects:
            lines.append(f"- `{s['name']}` — last touched {s['last_touched']} ({s['age_days']}d ago)")
        lines.append("")

    if stalled_schedules:
        lines.append("## Stalled scheduled jobs")
        lines.append("")
        for s in stalled_schedules:
            if s.get("age_hours") is None:
                lines.append(f"- `{s['job']}` (cron `{s['cron']}`) — {s['issue']}")
            else:
                lines.append(
                    f"- `{s['job']}` (cron `{s['cron']}`) — last output "
                    f"{s['last_output']}, {s['age_hours']}h ago "
                    f"(expected every {s['expected_within_hours']}h)"
                )
        lines.append("")

    if total == 0:
        lines.append("_Clean run — no drift detected._")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, help="Output path (default: life-agent/signals/YYYY-MM-DD-signals.md)")
    ap.add_argument("--stdout", action="store_true", help="Print to stdout instead of file")
    args = ap.parse_args()

    now = datetime.now(TZ)

    stale_topics = detect_stale_topics(now)
    broken_links = detect_broken_entity_links()
    name_dups = detect_near_duplicate_entity_names()
    dormant_projects = detect_dormant_projects(now)
    stalled_schedules = detect_stalled_schedules(now)

    report = build_report(
        now, stale_topics, broken_links, name_dups, dormant_projects, stalled_schedules
    )

    total = (
        len(stale_topics)
        + len(broken_links)
        + len(name_dups)
        + len(dormant_projects)
        + len(stalled_schedules)
    )

    if args.stdout:
        print(report)
        return

    if args.output:
        out_path = args.output
    else:
        signals_dir = DEPLOYED_DIR / "life-agent/signals"
        signals_dir.mkdir(parents=True, exist_ok=True)
        out_path = signals_dir / f"{now.strftime('%Y-%m-%d')}-signals.md"

    out_path.write_text(report)
    print(f"Wrote {out_path}")
    print(
        f"Signals: {total}  "
        f"(topics={len(stale_topics)} links={len(broken_links)} "
        f"names={len(name_dups)} projects={len(dormant_projects)} "
        f"schedules={len(stalled_schedules)})"
    )


if __name__ == "__main__":
    main()
