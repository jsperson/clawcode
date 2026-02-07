"""SKILL.md loader — parse, match, and format skills for prompt injection."""

from __future__ import annotations

import asyncio
import logging
import re
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


def parse_skill(path: Path) -> Skill | None:
    """Parse a SKILL.md file into a Skill object.

    Expected format:
    ---
    name: skill-name
    description: When to use this skill.
    allowed-tools: Bash(tool:*), Read, Edit
    metadata: {...}
    ---
    # Markdown body
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError) as e:
        logger.warning("Cannot read skill %s: %s", path, e)
        return None

    # Split YAML frontmatter from body
    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("Skill %s has no YAML frontmatter", path)
        return None

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

    return Skill(
        name=name,
        description=description,
        body=body,
        path=path,
        metadata=metadata,
        allowed_tools=allowed_tools,
        user_invocable=user_invocable,
    )


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


def match_skills(message: str, skills: list[Skill]) -> list[Skill]:
    """Match a user message against skill descriptions using keyword matching.

    Looks for keywords from the skill description in the user message.
    Returns skills sorted by match relevance (number of keyword hits).
    """
    message_lower = message.lower()
    scored: list[tuple[int, Skill]] = []

    for skill in skills:
        desc_lower = skill.description.lower()

        # Extract meaningful words from description (4+ chars to skip noise)
        keywords = set(re.findall(r"\b[a-z]{4,}\b", desc_lower))

        # Also extract quoted trigger phrases
        quoted = re.findall(r'"([^"]+)"', skill.description)
        phrases = [q.lower() for q in quoted]

        # Score: phrase matches count more than individual keywords
        score = 0
        for phrase in phrases:
            if phrase in message_lower:
                score += 5

        for kw in keywords:
            if kw in message_lower:
                score += 1

        if score > 0:
            scored.append((score, skill))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored]


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
