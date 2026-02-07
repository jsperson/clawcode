"""Schedule helpers — state tracking and listing.

Schedules are managed by launchd (macOS system scheduler).
Edit config/schedules.yaml and run scripts/schedule-sync.py to sync.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Chicago")
LABEL_PREFIX = "com.clawcode.schedule."


def _update_state(data_dir: Path, task_name: str) -> None:
    """Record last-run timestamp for a scheduled task."""
    state_path = data_dir / "state.json"
    try:
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        state = {}

    last_run = state.setdefault("last_run", {})
    last_run[task_name] = datetime.now(TZ).isoformat()

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))


def _load_schedules(config_dir: Path) -> dict:
    """Load schedule definitions from schedules.yaml."""
    path = config_dir / "schedules.yaml"
    if not path.exists():
        logger.warning("No schedules.yaml found at %s", path)
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("schedules", {})


def _get_launchd_status() -> dict[str, bool]:
    """Check which clawcode schedule agents are loaded in launchd.

    Returns a dict of {schedule_name: is_loaded}.
    """
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
        )
        loaded = {}
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[2].startswith(LABEL_PREFIX):
                name = parts[2][len(LABEL_PREFIX):]
                loaded[name] = True
        return loaded
    except Exception:
        return {}


def list_schedules(config_dir: Path, data_dir: Path) -> str:
    """Format a summary of all schedules with status and last-run times.

    Reads from schedules.yaml, state.json, and launchd status.
    """
    schedules = _load_schedules(config_dir)
    if not schedules:
        return "No schedules defined in config/schedules.yaml"

    # Load last-run state
    state_path = data_dir / "state.json"
    try:
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        state = {}
    last_runs = state.get("last_run", {})

    # Check launchd
    launchd_status = _get_launchd_status()

    lines = ["**Schedules**", ""]
    for name, sched in schedules.items():
        enabled = sched.get("enabled", True)
        cron = sched.get("cron", "?")
        loaded = launchd_status.get(name, False)

        if enabled and loaded:
            status = "active"
        elif enabled and not loaded:
            status = "enabled (not loaded — run schedule sync)"
        else:
            status = "disabled"

        last_run = last_runs.get(name, "never")

        lines.append(f"- **{name}** [{status}]")
        lines.append(f"  Cron: `{cron}` | Last run: {last_run}")

    return "\n".join(lines)
