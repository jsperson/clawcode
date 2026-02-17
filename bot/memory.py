"""Memory system — MEMORY.md, daily logs, file-locked writes."""

from __future__ import annotations

import fcntl
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Config

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Chicago")


def _today() -> date:
    return datetime.now(TZ).date()


def _memory_path(config: Config) -> Path:
    return Path(config.paths.project_dir) / "MEMORY.md"


def _daily_log_path(config: Config, d: date | None = None) -> Path:
    d = d or _today()
    return Path(config.paths.memory_dir) / f"{d.isoformat()}-discord.md"


def _template_path(config: Config) -> Path:
    return Path(config.paths.memory_dir) / "templates" / "daily.md"


def _read_file(path: Path) -> str:
    """Read file contents, return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_locked(path: Path, content: str) -> None:
    """Write content to file with exclusive file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _append_locked(path: Path, content: str) -> None:
    """Append content to file with exclusive file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_memory(config: Config) -> str:
    """Read MEMORY.md content."""
    return _read_file(_memory_path(config))


def read_daily_log(config: Config, d: date | None = None) -> str:
    """Read today's daily log. Creates from template if missing."""
    d = d or _today()
    path = _daily_log_path(config, d)

    if not path.exists():
        template = _read_file(_template_path(config))
        if template:
            content = template.replace("{date}", d.isoformat())
        else:
            content = f"# {d.isoformat()}\n\n## Summary\n\n## Key Decisions\n\n## Tasks Completed\n\n## Notable Information\n\n## Open Items\n"
        _write_locked(path, content)

    return _read_file(path)


def append_daily_log(config: Config, content: str, d: date | None = None) -> None:
    """Append content to today's daily log with file locking."""
    d = d or _today()
    path = _daily_log_path(config, d)

    # Ensure log exists first
    if not path.exists():
        read_daily_log(config, d)

    timestamp = datetime.now(TZ).strftime("%H:%M")
    entry = f"\n### {timestamp}\n{content}\n"
    _append_locked(path, entry)
    logger.info("Appended to daily log %s", path.name)


def update_memory(config: Config, section: str, content: str) -> None:
    """Update a section in MEMORY.md. Creates the section if it doesn't exist."""
    path = _memory_path(config)
    text = _read_file(path)

    # Find the section header (## or ### level)
    marker = f"### {section}"
    start = text.find(marker)

    if start == -1:
        # Section doesn't exist — append at end
        new_entry = f"\n{marker}\n**Date:** {_today().isoformat()}\n\n{content}\n"
        _append_locked(path, new_entry)
        logger.info("Added new memory section: %s", section)
    else:
        # Find the end of this section (next ### or ## heading, or EOF)
        next_heading = -1
        search_from = start + len(marker)
        for prefix in ("\n### ", "\n## ", "\n---"):
            idx = text.find(prefix, search_from)
            if idx != -1 and (next_heading == -1 or idx < next_heading):
                next_heading = idx

        if next_heading == -1:
            next_heading = len(text)

        new_section = f"{marker}\n**Date:** {_today().isoformat()}\n\n{content}\n"
        updated = text[:start] + new_section + text[next_heading:]
        _write_locked(path, updated)
        logger.info("Updated memory section: %s", section)


def remember(config: Config, fact: str) -> None:
    """Append a curated fact to MEMORY.md under a general section."""
    path = _memory_path(config)
    today = _today().isoformat()
    entry = f"\n### Remembered Fact\n**Date:** {today}\n\n{fact}\n\n---\n"
    _append_locked(path, entry)
    logger.info("Remembered: %s", fact[:60])
