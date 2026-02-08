"""SKILL.md loader — parse, gate, and format skills for prompt injection.

Supports both ClawCode and Clawdbot/ClewHub metadata namespaces.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path
    metadata: dict = field(default_factory=dict)
    allowed_tools: str = ""
    user_invocable: bool = False


def _get_skill_metadata(raw_metadata: dict) -> dict:
    """Extract skill metadata from either clawcode or clawdbot namespace.

    Checks metadata.clawcode first, then metadata.clawdbot as fallback.
    Returns the namespace dict (requires, os, emoji, etc.) or empty dict.
    """
    if not isinstance(raw_metadata, dict):
        return {}
    # Prefer clawcode namespace
    ns = raw_metadata.get("clawcode")
    if isinstance(ns, dict):
        return ns
    # Fall back to clawdbot namespace
    ns = raw_metadata.get("clawdbot")
    if isinstance(ns, dict):
        return ns
    return {}


def parse_skill(path: Path) -> Skill | None:
    """Parse a SKILL.md file into a Skill object.

    Supports two formats:
    1. YAML frontmatter (standard):
       ---
       name: skill-name
       description: When to use this skill.
       allowed-tools: Bash(tool:*), Read, Edit
       metadata: {...}
       ---
       # Markdown body

    2. No frontmatter (fallback):
       Derives name from directory, uses first heading as description.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError) as e:
        logger.warning("Cannot read skill %s: %s", path, e)
        return None

    # Try to split YAML frontmatter from body
    parts = text.split("---", 2)
    if len(parts) >= 3 and parts[0].strip() == "":
        # Has frontmatter
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            logger.warning("Bad YAML in skill %s: %s", path, e)
            return None

        if not isinstance(fm, dict):
            logger.warning("Skill %s frontmatter is not a dict", path)
            return None

        name = fm.get("name", path.parent.name)
        description = fm.get("description", "")
        body = parts[2].strip()
        metadata = fm.get("metadata", {})
        allowed_tools = fm.get("allowed-tools", "")
        user_invocable = fm.get("user-invocable", False)
    else:
        # No frontmatter — derive from content
        name = path.parent.name
        body = text.strip()
        metadata = {}
        allowed_tools = ""
        user_invocable = False

        # Extract description from first heading
        description = ""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                description = line[2:].strip()
                break

    return Skill(
        name=name,
        description=description,
        body=body,
        path=path,
        metadata=metadata,
        allowed_tools=allowed_tools,
        user_invocable=user_invocable,
    )


def check_eligible(skill: Skill) -> bool:
    """Check if a skill meets its requirements for the current platform.

    Gates on:
    - requires.bins: all listed binaries must be on PATH
    - requires.env: all listed env vars must be set
    - os: platform must match (darwin, linux, etc.)

    Works with both metadata.clawcode and metadata.clawdbot namespaces.
    """
    ns = _get_skill_metadata(skill.metadata)
    if not ns:
        return True  # No metadata = no requirements = eligible

    # OS platform filter
    os_filter = ns.get("os")
    if os_filter and isinstance(os_filter, list):
        current_platform = sys.platform
        if current_platform not in os_filter:
            logger.debug(
                "Skill %s skipped: platform %s not in %s",
                skill.name, current_platform, os_filter,
            )
            return False

    requires = ns.get("requires", {})
    if not isinstance(requires, dict):
        return True

    # Binary requirements
    bins = requires.get("bins", [])
    if isinstance(bins, list):
        for b in bins:
            if not shutil.which(str(b)):
                logger.debug("Skill %s skipped: binary %s not found", skill.name, b)
                return False

    # Environment variable requirements
    env_vars = requires.get("env", [])
    if isinstance(env_vars, list):
        for var in env_vars:
            if not os.environ.get(str(var)):
                logger.debug("Skill %s skipped: env var %s not set", skill.name, var)
                return False

    return True


def load_skills(skills_dir: str | Path) -> list[Skill]:
    """Scan skills/*/SKILL.md and return parsed skills."""
    skills_dir = Path(skills_dir)
    skills: list[Skill] = []

    if not skills_dir.is_dir():
        return skills

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill = parse_skill(skill_md)
        if skill:
            skills.append(skill)
            logger.debug("Loaded skill: %s", skill.name)

    logger.info("Loaded %d skills from %s", len(skills), skills_dir)
    return skills


def _substitute_arguments(body: str, arguments: str) -> str:
    """Replace $ARGUMENTS placeholder in skill body."""
    return body.replace("$ARGUMENTS", arguments)


async def _run_dynamic_context(body: str) -> str:
    """Execute !`command` inline commands and replace with output."""

    async def _exec_match(match: re.Match) -> str:
        cmd = match.group(1)
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            return stdout.decode("utf-8", errors="replace").strip()
        except Exception as e:
            logger.warning("Dynamic context command failed: %s — %s", cmd, e)
            return f"(command failed: {cmd})"

    # Find all !`command` patterns
    pattern = re.compile(r"!`([^`]+)`")
    matches = list(pattern.finditer(body))

    if not matches:
        return body

    # Execute all commands concurrently
    results = await asyncio.gather(
        *[_exec_match(m) for m in matches]
    )

    # Replace in reverse order to preserve positions
    for match, result in reversed(list(zip(matches, results))):
        body = body[:match.start()] + result + body[match.end():]

    return body


def format_skill_context(skills: list[Skill], arguments: str = "") -> str:
    """Format matched skills into prompt context for injection."""
    parts: list[str] = []
    for skill in skills:
        body = skill.body
        if arguments:
            body = _substitute_arguments(body, arguments)
        parts.append(f"## Skill: {skill.name}\n\n{body}")
    return "\n\n".join(parts)
