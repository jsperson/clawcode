#!/usr/bin/env python3
"""Sync schedules.yaml to macOS launchd agents.

Implements delete-all / re-push:
1. Find and unload all com.clawcode.schedule.* launchd agents
2. Delete their plist files
3. Read config/schedules.yaml
4. Generate and load new plist for each enabled schedule

Usage: schedule-sync.py
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parent.parent
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LABEL_PREFIX = "com.clawcode.schedule."


def get_uid() -> int:
    return os.getuid()


def find_existing_plists() -> list[Path]:
    """Find all com.clawcode.schedule.*.plist files."""
    if not LAUNCH_AGENTS_DIR.exists():
        return []
    return sorted(LAUNCH_AGENTS_DIR.glob(f"{LABEL_PREFIX}*.plist"))


def unload_and_remove(plists: list[Path]) -> None:
    """Unload each agent from launchd and delete the plist file."""
    uid = get_uid()
    gui_target = f"gui/{uid}"

    for plist in plists:
        label = plist.stem  # com.clawcode.schedule.<name>
        service_target = f"{gui_target}/{label}"

        # Try bootout (modern launchctl)
        result = subprocess.run(
            ["launchctl", "bootout", service_target],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  Unloaded: {label}")
        else:
            # May already be unloaded — that's fine
            if "No such process" not in result.stderr and "Could not find" not in result.stderr:
                print(f"  Warning unloading {label}: {result.stderr.strip()}")

        plist.unlink(missing_ok=True)
        print(f"  Removed:  {plist.name}")


def parse_cron_field(field: str, valid_range: tuple[int, int]) -> list[int] | None:
    """Parse a single cron field into a list of integers.

    Returns None for '*' (any value).
    Supports: *, N, N-M, */N, N,M,O
    """
    if field == "*":
        return None

    # */N — step values
    if field.startswith("*/"):
        step = int(field[2:])
        lo, hi = valid_range
        return list(range(lo, hi + 1, step))

    # N-M — range
    if "-" in field and "," not in field:
        parts = field.split("-")
        return list(range(int(parts[0]), int(parts[1]) + 1))

    # N,M,O — list
    if "," in field:
        return [int(x) for x in field.split(",")]

    # Single value
    return [int(field)]


def cron_to_calendar_intervals(cron_expr: str) -> list[dict] | None:
    """Convert a 5-field cron expression to launchd StartCalendarInterval dicts.

    Returns None if the expression uses step intervals that are better
    served by StartInterval (e.g., */30).
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron: {cron_expr}")

    minute, hour, dom, month, dow = parts

    # For simple step-only patterns like "*/30 * * * *", use StartInterval
    if (minute.startswith("*/") and hour == "*" and dom == "*"
            and month == "*" and dow == "*"):
        step = int(minute[2:])
        return None  # signal to use StartInterval

    minutes = parse_cron_field(minute, (0, 59))
    hours = parse_cron_field(hour, (0, 23))
    days = parse_cron_field(dom, (1, 31))
    months = parse_cron_field(month, (1, 12))
    weekdays = parse_cron_field(dow, (0, 6))

    # Build all combinations — launchd needs explicit entries
    intervals: list[dict] = []

    minute_vals = minutes or [None]
    hour_vals = hours or [None]
    day_vals = days or [None]
    month_vals = months or [None]
    weekday_vals = weekdays or [None]

    for mn in minute_vals:
        for hr in hour_vals:
            for dy in day_vals:
                for mo in month_vals:
                    for wd in weekday_vals:
                        entry: dict = {}
                        if mn is not None:
                            entry["Minute"] = mn
                        if hr is not None:
                            entry["Hour"] = hr
                        if dy is not None:
                            entry["Day"] = dy
                        if mo is not None:
                            entry["Month"] = mo
                        if wd is not None:
                            entry["Weekday"] = wd
                        intervals.append(entry)

    return intervals


def cron_to_start_interval(cron_expr: str) -> int | None:
    """For step-only cron expressions, return interval in seconds."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return None

    minute, hour, dom, month, dow = parts

    if (minute.startswith("*/") and hour == "*" and dom == "*"
            and month == "*" and dow == "*"):
        return int(minute[2:]) * 60

    return None


def generate_plist(name: str, cron_expr: str) -> dict:
    """Generate a launchd plist dict for a schedule."""
    label = f"{LABEL_PREFIX}{name}"

    # Find the venv python
    venv_python = str(PROJECT_DIR / ".venv" / "bin" / "python")
    runner_script = str(PROJECT_DIR / "scripts" / "schedule-runner.py")

    # Log files
    log_dir = PROJECT_DIR / "data" / "logs"

    plist: dict = {
        "Label": label,
        "ProgramArguments": [venv_python, runner_script, name],
        "WorkingDirectory": str(PROJECT_DIR),
        "StandardOutPath": str(log_dir / f"schedule-{name}.log"),
        "StandardErrorPath": str(log_dir / f"schedule-{name}.log"),
        "EnvironmentVariables": {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
            "HOME": str(Path.home()),
        },
    }

    # Determine schedule type
    interval_secs = cron_to_start_interval(cron_expr)
    if interval_secs is not None:
        plist["StartInterval"] = interval_secs
    else:
        intervals = cron_to_calendar_intervals(cron_expr)
        if intervals:
            if len(intervals) == 1:
                plist["StartCalendarInterval"] = intervals[0]
            else:
                plist["StartCalendarInterval"] = intervals

    return plist


def load_schedules() -> dict:
    """Load schedule definitions from config/schedules.yaml."""
    path = PROJECT_DIR / "config" / "schedules.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("schedules", {})


def main() -> None:
    print("ClawCode Schedule Sync")
    print("=" * 40)

    # Ensure LaunchAgents dir exists
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure log directory exists
    log_dir = PROJECT_DIR / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Remove all existing clawcode schedule agents
    existing = find_existing_plists()
    if existing:
        print(f"\nRemoving {len(existing)} existing schedule agent(s)...")
        unload_and_remove(existing)
    else:
        print("\nNo existing schedule agents found.")

    # Step 2: Load schedules
    schedules = load_schedules()
    if not schedules:
        print("\nNo schedules defined in config/schedules.yaml")
        return

    # Step 3: Create and load new agents
    uid = get_uid()
    gui_target = f"gui/{uid}"
    installed = 0
    skipped = 0

    print(f"\nProcessing {len(schedules)} schedule(s)...")
    for name, sched in schedules.items():
        if not sched.get("enabled", True):
            print(f"  Skipped (disabled): {name}")
            skipped += 1
            continue

        cron_expr = sched["cron"]

        try:
            plist_data = generate_plist(name, cron_expr)
            label = plist_data["Label"]
            plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"

            # Write plist
            with open(plist_path, "wb") as f:
                plistlib.dump(plist_data, f)

            # Load into launchd
            result = subprocess.run(
                ["launchctl", "bootstrap", gui_target, str(plist_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print(f"  Installed: {name} ({cron_expr})")
                installed += 1
            else:
                print(f"  Error loading {name}: {result.stderr.strip()}")

        except Exception as e:
            print(f"  Error processing {name}: {e}")

    # Summary
    print(f"\n{'=' * 40}")
    print(f"Installed: {installed}  Skipped: {skipped}  Total: {len(schedules)}")

    if installed > 0:
        print(f"\nVerify with: launchctl list | grep clawcode.schedule")
        print(f"Logs at:     {PROJECT_DIR}/data/logs/schedule-*.log")


if __name__ == "__main__":
    main()
