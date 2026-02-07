"""ClawCode Discord bot — main entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord

from .claude_bridge import ClaudeBridge
from .config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Discord message splitting — respect 2000 char limit
# ---------------------------------------------------------------------------

MAX_DISCORD_LEN = 2000
SAFE_LEN = 1900  # leave room for formatting


def split_message(text: str) -> list[str]:
    """Split a long message for Discord's 2000-character limit.

    Tries to split on paragraph boundaries, then line boundaries,
    then hard-splits at SAFE_LEN.
    """
    if len(text) <= MAX_DISCORD_LEN:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= SAFE_LEN:
            chunks.append(remaining)
            break

        # Try paragraph boundary
        cut = remaining.rfind("\n\n", 0, SAFE_LEN)
        if cut > 0:
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip("\n")
            continue

        # Try line boundary
        cut = remaining.rfind("\n", 0, SAFE_LEN)
        if cut > 0:
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip("\n")
            continue

        # Hard split
        chunks.append(remaining[:SAFE_LEN])
        remaining = remaining[SAFE_LEN:]

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------


def create_bot(config: Config) -> discord.Client:
    """Create and configure the Discord bot client."""
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    bridge = ClaudeBridge(config)

    # Store references for later phases (scheduler, file watcher)
    client.config = config  # type: ignore[attr-defined]
    client.bridge = bridge  # type: ignore[attr-defined]

    @client.event
    async def on_ready() -> None:
        logger.info("ClawCode bot connected as %s", client.user)

    @client.event
    async def on_message(message: discord.Message) -> None:
        # Ignore own messages
        if message.author == client.user:
            return

        # Only respond in configured channel
        if message.channel.id != config.discord.channel_id:
            return

        # Only respond in configured guild
        if message.guild and message.guild.id != config.discord.guild_id:
            return

        user_text = message.content.strip()
        if not user_text:
            return

        logger.info("Message from %s: %s", message.author, user_text[:100])

        # Show typing indicator while Claude processes
        async with message.channel.typing():
            try:
                # Build context from memory and skills if available
                append_prompt = await _build_context(config, user_text)

                response = await bridge.invoke(
                    message=user_text,
                    channel_id=str(message.channel.id),
                    append_prompt=append_prompt,
                )

                # Send response, splitting if needed
                for chunk in split_message(response):
                    await message.channel.send(chunk)

            except TimeoutError:
                await message.channel.send(
                    "Timed out waiting for Claude Code. Try again or simplify the request."
                )
            except RuntimeError as e:
                logger.exception("Claude Code error")
                await message.channel.send(f"Error from Claude Code: {e}")
            except Exception:
                logger.exception("Unexpected error processing message")
                await message.channel.send(
                    "Something went wrong. Check the logs for details."
                )

    return client


async def _build_context(config: Config, user_message: str) -> str | None:
    """Build the append-system-prompt context from memory and skills.

    Returns None if no context modules are available yet.
    """
    parts: list[str] = []

    # Memory integration (Phase 3)
    try:
        from .memory import read_memory, read_daily_log

        mem = read_memory(config)
        if mem:
            parts.append(f"## Memory\n{mem}")
        daily = read_daily_log(config)
        if daily:
            parts.append(f"## Today's Log\n{daily}")
    except ImportError:
        pass

    # Skill integration (Phase 4)
    try:
        from skills.loader import load_skills, match_skills, format_skill_context

        all_skills = load_skills(config.paths.skills_dir)
        matched = match_skills(user_message, all_skills)
        if matched:
            skill_ctx = format_skill_context(matched)
            parts.append(skill_ctx)
    except ImportError:
        pass

    return "\n\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the ClawCode Discord bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        config = Config.load()
    except Exception:
        logger.exception("Failed to load configuration")
        sys.exit(1)

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not set in environment or .env")
        sys.exit(1)

    client = create_bot(config)

    # Start scheduler and file watcher if available (Phases 6-7)
    original_setup_hook = client.setup_hook if hasattr(client, "setup_hook") else None

    async def setup_hook() -> None:
        if original_setup_hook:
            await original_setup_hook()

        # MCP servers
        if config.mcp.servers:
            for s in config.mcp.servers:
                logger.info("MCP server configured: %s (%s)", s.name, s.transport)
        else:
            logger.info("No MCP servers configured")

        # Phase 6: Scheduler
        try:
            from .scheduler import start_scheduler
            await start_scheduler(client)
            logger.info("Scheduler started")
        except ImportError:
            logger.debug("Scheduler not yet available")

        # Phase 7: File watcher
        try:
            from .file_watcher import start_file_watcher
            start_file_watcher(client)
            logger.info("File watcher started")
        except ImportError:
            logger.debug("File watcher not yet available")

    client.setup_hook = setup_hook  # type: ignore[method-assign]

    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
