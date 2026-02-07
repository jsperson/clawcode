"""Scheduled tasks — APScheduler cron triggers invoking Claude Code."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Chicago")


def _parse_cron(expr: str) -> dict:
    """Parse a standard cron expression into APScheduler kwargs.

    Format: minute hour day_of_month month day_of_week
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def _load_schedules(config_dir: Path) -> dict:
    """Load schedule definitions from schedules.yaml."""
    path = config_dir / "schedules.yaml"
    if not path.exists():
        logger.warning("No schedules.yaml found at %s", path)
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("schedules", {})


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


# Store client reference for scheduler callbacks
_client: discord.Client | None = None


def _run_scheduled_task_sync(task_name: str, prompt: str) -> None:
    """Wrapper that schedules the async task on the bot's event loop."""
    if _client is None:
        logger.error("Client not set for scheduled task: %s", task_name)
        return
    asyncio.ensure_future(_run_scheduled_task(_client, task_name, prompt))


async def _run_scheduled_task(
    client: discord.Client,
    task_name: str,
    prompt: str,
) -> None:
    """Execute a scheduled task: invoke Claude, post result to Discord."""
    config = client.config  # type: ignore[attr-defined]
    bridge = client.bridge  # type: ignore[attr-defined]

    logger.info("Running scheduled task: %s", task_name)

    try:
        response = await bridge.invoke_scheduled(prompt=prompt)

        # Post to configured Discord channel
        channel = client.get_channel(config.discord.channel_id)
        if channel:
            from .main import split_message

            header = f"**Scheduled: {task_name}**\n"
            for chunk in split_message(header + response):
                await channel.send(chunk)
        else:
            logger.error("Cannot find Discord channel %d", config.discord.channel_id)

        _update_state(Path(config.paths.data_dir), task_name)
        logger.info("Scheduled task completed: %s", task_name)

    except Exception:
        logger.exception("Scheduled task failed: %s", task_name)

        try:
            channel = client.get_channel(config.discord.channel_id)
            if channel:
                await channel.send(
                    f"**Scheduled task failed: {task_name}**\nCheck logs for details."
                )
        except Exception:
            logger.exception("Failed to post error to Discord")


async def start_scheduler(client: discord.Client) -> AsyncIOScheduler:
    """Load schedules and start the APScheduler."""
    global _client
    _client = client

    config = client.config  # type: ignore[attr-defined]
    config_dir = Path(config.paths.project_dir) / "config"
    schedules = _load_schedules(config_dir)

    scheduler = AsyncIOScheduler(timezone=TZ)

    for name, sched in schedules.items():
        if not sched.get("enabled", True):
            logger.info("Skipping disabled schedule: %s", name)
            continue

        cron_expr = sched["cron"]
        prompt = sched["prompt"]

        try:
            cron_kwargs = _parse_cron(cron_expr)
            trigger = CronTrigger(timezone=TZ, **cron_kwargs)

            scheduler.add_job(
                _run_scheduled_task_sync,
                trigger,
                id=name,
                kwargs={"task_name": name, "prompt": prompt},
                replace_existing=True,
            )
            logger.info("Registered schedule: %s (%s)", name, cron_expr)

        except Exception:
            logger.exception("Failed to register schedule: %s", name)

    scheduler.start()
    logger.info("Scheduler started with %d tasks", len(schedules))

    client._scheduler = scheduler  # type: ignore[attr-defined]
    return scheduler
