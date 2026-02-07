#!/usr/bin/env python3
"""Run a single scheduled task — invoked by launchd.

Usage: schedule-runner.py <task-name>

Loads the task definition from config/schedules.yaml, invokes Claude Code CLI,
posts the result to Discord via REST API, and updates state.json.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Resolve project root (scripts/ lives one level below)
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import yaml  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

TZ = ZoneInfo("America/Chicago")
MAX_DISCORD_LEN = 2000
SAFE_LEN = 1900

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("schedule-runner")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_env() -> None:
    """Load .env from project root."""
    load_dotenv(PROJECT_DIR / ".env")


def load_schedules() -> dict:
    """Load schedule definitions from config/schedules.yaml."""
    path = PROJECT_DIR / "config" / "schedules.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("schedules", {})


def load_config() -> dict:
    """Load main config values we need."""
    path = PROJECT_DIR / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def expand_path(p: str) -> str:
    return str(Path(p).expanduser())


def split_message(text: str) -> list[str]:
    """Split for Discord's 2000-char limit."""
    if len(text) <= MAX_DISCORD_LEN:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= SAFE_LEN:
            chunks.append(remaining)
            break

        cut = remaining.rfind("\n\n", 0, SAFE_LEN)
        if cut > 0:
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip("\n")
            continue

        cut = remaining.rfind("\n", 0, SAFE_LEN)
        if cut > 0:
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip("\n")
            continue

        chunks.append(remaining[:SAFE_LEN])
        remaining = remaining[SAFE_LEN:]

    return [c for c in chunks if c.strip()]


def update_state(task_name: str) -> None:
    """Record last-run timestamp in data/state.json."""
    data_dir = Path(expand_path("~/clawcode/data"))
    state_path = data_dir / "state.json"
    try:
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        state = {}

    last_run = state.setdefault("last_run", {})
    last_run[task_name] = datetime.now(TZ).isoformat()

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def build_context() -> str | None:
    """Build system prompt context from memory files."""
    parts: list[str] = []

    memory_path = PROJECT_DIR / "MEMORY.md"
    if memory_path.exists():
        parts.append(f"## Memory\n{memory_path.read_text()}")

    daily_path = PROJECT_DIR / "memory" / f"{datetime.now(TZ).strftime('%Y-%m-%d')}.md"
    if daily_path.exists():
        parts.append(f"## Today's Log\n{daily_path.read_text()}")

    return "\n\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Claude CLI invocation
# ---------------------------------------------------------------------------


def invoke_claude(prompt: str, config: dict) -> str:
    """Run Claude Code CLI and return the response text."""
    claude_path = expand_path(config["claude"]["path"])
    project_dir = expand_path(config["paths"]["project_dir"])
    vault_path = expand_path(config["vault"]["path"])

    cmd = [
        claude_path,
        "--print",
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--add-dir", vault_path,
    ]

    # MCP config
    mcp_config_path = Path(expand_path(config["paths"]["data_dir"])) / ".mcp-config.json"
    if mcp_config_path.exists():
        cmd.extend(["--mcp-config", str(mcp_config_path)])

    # System context
    context = build_context()
    if context:
        cmd.extend(["--append-system-prompt", context])

    logger.info("Running: %s", " ".join(cmd[:4]) + " ...")

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=project_dir,
        timeout=600,
    )

    if result.returncode != 0:
        logger.error("Claude CLI failed (rc=%d): %s", result.returncode, result.stderr)
        raise RuntimeError(f"Claude CLI exited {result.returncode}: {result.stderr}")

    # Parse JSON response
    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        if isinstance(data, dict) and "content" in data:
            parts = []
            for block in data["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
    except json.JSONDecodeError:
        pass

    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Discord REST API
# ---------------------------------------------------------------------------


def post_to_discord(channel_id: str, message: str, bot_token: str) -> None:
    """Post a message to Discord via REST API (no discord.py needed)."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }

    for chunk in split_message(message):
        body = json.dumps({"content": chunk}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status not in (200, 201):
                    logger.error("Discord API returned %d", resp.status)
        except urllib.error.HTTPError as e:
            logger.error("Discord API error: %d %s", e.code, e.read().decode())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: schedule-runner.py <task-name>", file=sys.stderr)
        sys.exit(1)

    task_name = sys.argv[1]
    load_env()

    # Load schedules
    schedules = load_schedules()
    if task_name not in schedules:
        logger.error("Unknown task: %s", task_name)
        sys.exit(1)

    task = schedules[task_name]
    if not task.get("enabled", True):
        logger.info("Task %s is disabled, skipping", task_name)
        sys.exit(0)

    prompt = task["prompt"]
    config = load_config()

    # Get Discord credentials
    bot_token = os.environ.get("DISCORD_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")

    logger.info("Running scheduled task: %s", task_name)

    try:
        response = invoke_claude(prompt, config)

        # Post to Discord if credentials available
        if bot_token and channel_id:
            header = f"**Scheduled: {task_name}**\n"
            post_to_discord(channel_id, header + response, bot_token)
        else:
            logger.warning("Discord credentials not set, skipping post")

        # Print response to stdout (captured by launchd log)
        print(response)

        update_state(task_name)
        logger.info("Scheduled task completed: %s", task_name)

    except Exception:
        logger.exception("Scheduled task failed: %s", task_name)

        # Try to notify Discord of failure
        if bot_token and channel_id:
            try:
                post_to_discord(
                    channel_id,
                    f"**Scheduled task failed: {task_name}**\nCheck logs: `clawcode schedule logs {task_name}`",
                    bot_token,
                )
            except Exception:
                logger.exception("Failed to post error to Discord")

        sys.exit(1)


if __name__ == "__main__":
    main()
