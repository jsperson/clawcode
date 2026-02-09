"""Unified context builder — assembles system prompt context and manages cache.

Builds the --append-system-prompt string from identity files and skill summaries.
Used by both the Discord bot (in-memory + file cache) and the CLI (file cache only).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)


def build_context(config: Config) -> str:
    """Build the full system prompt context from disk.

    Assembles:
    - SOUL.md (core philosophy and values)
    - STYLE.md (voice and communication patterns)
    - IDENTITY.md (external presentation)
    - USER.md (user profile)
    - Eligible skill names + descriptions (summary only, not full bodies)

    Returns the formatted context string.
    """
    parts: list[str] = []

    # Soul — core philosophy (loaded first, most foundational)
    soul_path = Path(config.paths.project_dir) / "SOUL.md"
    soul = _read_file(soul_path)
    if soul:
        parts.append(f"## Soul\n{soul}")

    # Style — voice and communication patterns
    style_path = Path(config.paths.project_dir) / "STYLE.md"
    style = _read_file(style_path)
    if style:
        parts.append(f"## Style\n{style}")

    # Identity — external presentation
    identity_path = Path(config.paths.project_dir) / "IDENTITY.md"
    identity = _read_file(identity_path)
    if identity:
        parts.append(f"## Identity\n{identity}")

    # User profile
    user_path = Path(config.paths.project_dir) / "USER.md"
    user = _read_file(user_path)
    if user:
        parts.append(f"## User Profile\n{user}")

    # Skill summaries (names + descriptions of eligible skills)
    try:
        from skills.loader import load_skills, check_eligible

        all_skills = load_skills(config.paths.skills_dir)
        eligible = [s for s in all_skills if check_eligible(s)]
        if eligible:
            lines = ["## Available Skills", ""]
            lines.append(
                "The following skills are available. To use a skill, "
                "read its SKILL.md file for full instructions."
            )
            lines.append("")
            for skill in eligible:
                skill_path = str(skill.path)
                lines.append(f"- **{skill.name}**: {skill.description} (`{skill_path}`)")
            parts.append("\n".join(lines))
            logger.info("Context includes %d eligible skills", len(eligible))
    except ImportError:
        logger.debug("Skills loader not available")

    # Memory search instructions
    parts.append(
        "## Memory Search\n\n"
        "When you need past decisions, preferences, or historical context, "
        "run `clawcode memory search \"<query>\"` before reading files directly. "
        "Use `--source memory` for curated knowledge, `--source daily` for logs. "
        "Use `--limit 10` if 5 results aren't enough. "
        "Fall back to reading MEMORY.md directly if search returns nothing."
    )

    context = "\n\n".join(parts)
    logger.info("Built context: %d chars", len(context))
    return context


def write_cache(config: Config, context: str) -> None:
    """Write context to data/context.cache."""
    cache_path = _cache_path(config)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(context, encoding="utf-8")
    logger.info("Wrote context cache: %s (%d chars)", cache_path, len(context))


def read_cache(config: Config) -> str | None:
    """Read cached context from data/context.cache.

    Returns None if cache doesn't exist.
    """
    cache_path = _cache_path(config)
    if not cache_path.exists():
        return None
    try:
        content = cache_path.read_text(encoding="utf-8")
        return content if content.strip() else None
    except OSError as e:
        logger.warning("Failed to read context cache: %s", e)
        return None


def _cache_path(config: Config) -> Path:
    return Path(config.paths.data_dir) / "context.cache"


def _read_file(path: Path) -> str:
    """Read file contents, return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError):
        return ""
