"""ClawCode Discord bot — main entry point."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from .claude_bridge import ClaudeBridge, ContextTooLargeError
from .config import Config
from .context import build_context, write_cache
from .gateway_client import GatewayClient

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Chicago")

# ---------------------------------------------------------------------------
# Bot state helpers
# ---------------------------------------------------------------------------


def _update_bot_state(config: Config, event: str) -> None:
    """Write a bot lifecycle event to data/state.json."""
    state_path = Path(config.paths.data_dir) / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        state = {}
    state[event] = datetime.now(TZ).isoformat()
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Conversation logging — append exchanges to daily log
# ---------------------------------------------------------------------------


def _log_conversation(
    config: Config,
    author: str,
    user_text: str,
    attachments: list[dict],
    response: str | None,
) -> None:
    """Log a Discord conversation exchange to today's daily log."""
    try:
        from .memory import append_daily_log

        parts = [f"**{author}:** {user_text}" if user_text else f"**{author}:** *(no text)*"]
        if attachments:
            names = ", ".join(a["filename"] for a in attachments)
            parts.append(f"*Attachments: {names}*")
        parts.append("")  # blank line
        if response:
            # Truncate very long responses to keep logs manageable
            if len(response) > 2000:
                parts.append(f"**Computer:** {response[:2000]}… *(truncated, {len(response)} chars)*")
            else:
                parts.append(f"**Computer:** {response}")
        else:
            parts.append("**Computer:** *(no response — error)*")

        append_daily_log(config, "\n".join(parts))
    except Exception:
        logger.debug("Failed to log conversation", exc_info=True)


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
# Context cache management
# ---------------------------------------------------------------------------

# Module-level cached context — built once at startup, refreshed on file
# changes or !reload. Avoids per-message disk reads.
_cached_context: str | None = None


def _refresh_context(config: Config) -> str:
    """Rebuild context from disk, update in-memory cache and file cache."""
    global _cached_context
    context = build_context(config)
    _cached_context = context
    write_cache(config, context)
    logger.info("Context cache refreshed (%d chars)", len(context))
    return context


# ---------------------------------------------------------------------------
# Discord attachment handling
# ---------------------------------------------------------------------------

IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
TEXT_EXTENSIONS = {
    ".py", ".txt", ".json", ".csv", ".md", ".yaml", ".yml",
    ".js", ".ts", ".html", ".css", ".sh", ".rb", ".rs",
    ".go", ".swift", ".sql", ".xml", ".toml", ".ini", ".log",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ATTACHMENTS = 5
ATTACHMENT_DIR = Path("/tmp/clawcode-attachments")

_INBOUND_NOTES_DIR = Path.home() / (
    "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
    "/Personal Notes/Inbound Notes"
)


def _is_notes_request(text: str) -> bool:
    """Check if the message is asking to process handwritten notes."""
    lower = text.lower()
    return "process" in lower and "note" in lower


def _detect_image_type(data: bytes) -> str | None:
    """Detect image type from magic bytes. Returns MIME type or None."""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if data[:2] == b'\xff\xd8':
        return "image/jpeg"
    if data[:4] == b'GIF8':
        return "image/gif"
    if data[:4] == b'RIFF' and len(data) > 12 and data[8:12] == b'WEBP':
        return "image/webp"
    return None


async def _download_attachments(discord_attachments: list) -> list[dict]:
    """Download and encode Discord attachments for the gateway.

    Images → base64 image content blocks (inline, Claude sees them directly).
    Text files → base64 text content blocks (decoded by gateway).
    Everything else → saved to /tmp/clawcode-attachments/, referenced by path
                      so Claude can access them with its Read tool.
    """
    results = []
    for att in discord_attachments[:MAX_ATTACHMENTS]:
        if att.size > MAX_FILE_SIZE:
            logger.warning("Skipping oversized attachment: %s (%d bytes)", att.filename, att.size)
            continue

        content_type = att.content_type or ""
        ext = Path(att.filename).suffix.lower()
        is_image = content_type.startswith("image/")
        is_text = ext in TEXT_EXTENSIONS

        try:
            data = await att.read()
        except Exception:
            logger.warning("Failed to download attachment: %s", att.filename)
            continue

        if is_image:
            detected = _detect_image_type(data)
            if not detected:
                continue  # not a valid image
            content_type = detected  # trust magic bytes over extension
            results.append({
                "filename": att.filename,
                "content_type": content_type,
                "data": base64.b64encode(data).decode("ascii"),
            })
        elif is_text:
            results.append({
                "filename": att.filename,
                "content_type": "text/plain",
                "data": base64.b64encode(data).decode("ascii"),
            })
        else:
            # Binary file — save to /tmp and reference by path
            saved = _save_attachment(att.filename, data)
            if saved:
                ref = f"[File saved: {saved}] — use your Read tool to access this file"
                results.append({
                    "filename": att.filename,
                    "content_type": "text/plain",
                    "data": base64.b64encode(ref.encode("utf-8")).decode("ascii"),
                })

        logger.info("Attachment: %s (%d bytes, %s)", att.filename, len(data), content_type)

    return results


def _save_attachment(
    filename: str, data: bytes, dest_dir: Path = ATTACHMENT_DIR
) -> str | None:
    """Save an attachment to the given directory. Returns the path or None."""
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize filename — keep only the basename, no path traversal
        safe_name = Path(filename).name
        if not safe_name:
            safe_name = "attachment"
        dest = dest_dir / safe_name
        # Avoid collisions — append counter if file exists
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            i = 1
            while dest.exists():
                dest = dest_dir / f"{stem}_{i}{suffix}"
                i += 1
        dest.write_bytes(data)
        return str(dest)
    except Exception:
        logger.warning("Failed to save attachment: %s", filename)
        return None


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------


_VAULT_REVIEWS_DIR = Path.home() / (
    "Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
    "/Projects/ClawCode-Autonomy/reviews"
)


def _log_heartbeat_to_vault(response: str, is_silent: bool) -> None:
    """Append heartbeat output to a daily log in the Obsidian vault."""
    try:
        _VAULT_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now(TZ)
        log_path = _VAULT_REVIEWS_DIR / f"{now.strftime('%Y-%m-%d')}-heartbeat.md"

        timestamp = now.strftime("%H:%M")
        if is_silent:
            entry = f"### {timestamp} — ok (silent)\n\n"
        else:
            entry = f"### {timestamp}\n\n{response}\n\n---\n\n"

        # Create file with header if new, otherwise append
        if not log_path.exists():
            header = f"# Heartbeat Log — {now.strftime('%Y-%m-%d')}\n\n"
            log_path.write_text(header + entry, encoding="utf-8")
        else:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(entry)

        logger.debug("Heartbeat logged to vault: %s", log_path.name)
    except Exception:
        logger.debug("Failed to log heartbeat to vault", exc_info=True)


def create_bot(config: Config) -> discord.Client:
    """Create and configure the Discord bot client."""
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    bridge = ClaudeBridge(config)
    gw_client: GatewayClient | None = None

    if config.gateway.enabled:
        gw_client = GatewayClient(
            host=config.gateway.host,
            port=config.gateway.port,
            auth_token=config.gateway.auth_token,
            sessions_path=str(Path(config.paths.data_dir) / "gateway-sessions.json"),
        )

    # Store references for later phases (scheduler, file watcher)
    client.config = config  # type: ignore[attr-defined]
    client.bridge = bridge  # type: ignore[attr-defined]
    client.gw_client = gw_client  # type: ignore[attr-defined]

    @client.event
    async def on_ready() -> None:
        logger.info("ClawCode bot connected as %s", client.user)
        _update_bot_state(config, "bot_started_at")

        # Build and cache context at startup
        _refresh_context(config)

        try:
            from .memory import append_daily_log
            append_daily_log(config, "Bot startup (graceful)")
        except ImportError:
            pass

        # Connect to gateway if enabled
        restored = 0
        if gw_client:
            ok = await gw_client.connect()
            if ok:
                restored = gw_client.session_count
                logger.info("Bot connected to gateway (%d sessions restored)", restored)
            else:
                logger.warning("Gateway connection failed — falling back to direct invocation")

        # Notify Discord channel
        try:
            channel = await client.fetch_channel(config.discord.channel_id)
            if restored:
                await channel.send(f"\U0001f7e2 Online. ({restored} session{'s' if restored != 1 else ''} restored)")
            else:
                await channel.send("\U0001f7e2 Online.")
        except Exception:
            logger.exception("Error sending startup message")

        # Start in-process heartbeat loop
        nonlocal _heartbeat_task
        if config.heartbeat.in_process.enabled:
            # Seed HEARTBEAT.md from template if it doesn't exist
            hb_path = Path(config.paths.project_dir) / "HEARTBEAT.md"
            hb_template = Path(config.paths.project_dir) / "HEARTBEAT.md.template"
            if not hb_path.exists() and hb_template.exists():
                shutil.copy2(hb_template, hb_path)
                logger.info("Seeded HEARTBEAT.md from template")

            # Seed proposals directory if it doesn't exist
            proposals_dir = Path(config.paths.project_dir) / "proposals"
            proposals_dir.mkdir(exist_ok=True)
            (proposals_dir / "archive").mkdir(exist_ok=True)

            _heartbeat_task = asyncio.create_task(_heartbeat_loop())
            logger.info("In-process heartbeat started (interval=%dm)",
                        config.heartbeat.in_process.interval_minutes)

    async def _shutdown() -> None:
        """Run cleanup before the bot process exits."""
        nonlocal _heartbeat_task
        logger.info("Bot shutting down — running cleanup")

        # 0a. Cancel heartbeat loop
        if _heartbeat_task and not _heartbeat_task.done():
            _heartbeat_task.cancel()
            try:
                await _heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("Heartbeat loop stopped")
            _heartbeat_task = None

        # 0b. Notify Discord channel before closing
        try:
            if not client.is_closed():
                channel = await client.fetch_channel(config.discord.channel_id)
                await channel.send("\U0001f534 Going offline.")
        except Exception:
            logger.exception("Error sending shutdown message")

        # 1. Disconnect gateway client
        if gw_client and gw_client.connected:
            try:
                await gw_client.disconnect()
            except Exception:
                logger.exception("Error disconnecting gateway client")

        # 2. Stop file watcher
        observer = getattr(client, "_file_observer", None)
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=5)
                logger.info("File watcher stopped")
            except Exception:
                logger.exception("Error stopping file watcher")

        # 3. Save sessions
        try:
            bridge.save_sessions()
        except Exception:
            logger.exception("Error saving sessions")

        # 4. Append shutdown marker to daily log
        try:
            from .memory import append_daily_log
            append_daily_log(config, "Bot shutdown (graceful)")
        except Exception:
            logger.exception("Error writing shutdown log")

        # 5. Write bot_stopped_at to state.json
        _update_bot_state(config, "bot_stopped_at")
        logger.info("Cleanup complete")

        # 6. Close the Discord client
        if not client.is_closed():
            await client.close()

    # Expose for signal handler
    client._shutdown = _shutdown  # type: ignore[attr-defined]

    # -------------------------------------------------------------------
    # Non-blocking message processing state (per-channel)
    # -------------------------------------------------------------------
    _active_tasks: dict[int, asyncio.Task] = {}       # channel_id → running task
    _message_queues: dict[int, asyncio.Queue] = {}    # channel_id → pending messages
    _cancel_events: dict[int, asyncio.Event] = {}     # channel_id → cancel signal
    _task_start_times: dict[int, float] = {}          # channel_id → monotonic start
    MAX_QUEUE_SIZE = 5
    STREAM_EDIT_INTERVAL = 3.0   # seconds between Discord message edits
    STREAM_MSG_LIMIT = 1800      # chars before splitting to a new message

    # -------------------------------------------------------------------
    # Heartbeat state
    # -------------------------------------------------------------------
    _last_user_message_time: float = 0.0   # monotonic, updated on every user message
    _heartbeat_task: asyncio.Task | None = None
    _heartbeat_count: int = 0              # cycles since startup, for full-scan cadence

    def _get_queue(channel_id: int) -> asyncio.Queue:
        if channel_id not in _message_queues:
            _message_queues[channel_id] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        return _message_queues[channel_id]

    def _get_cancel_event(channel_id: int) -> asyncio.Event:
        if channel_id not in _cancel_events:
            _cancel_events[channel_id] = asyncio.Event()
        return _cancel_events[channel_id]

    # -------------------------------------------------------------------
    # Streaming gateway response → progressive Discord edits
    # -------------------------------------------------------------------

    async def _stream_gateway_response(
        channel: discord.TextChannel,
        channel_id_str: str,
        user_text: str,
        attachments: list[dict] | None,
        cancel_event: asyncio.Event,
    ) -> str | None:
        """Stream gateway response with progressive Discord message edits.

        Returns the complete response text, or None on error/cancel.
        """
        status_msg = await channel.send("*thinking...*")
        accumulated = ""
        last_edit = asyncio.get_event_loop().time()
        sent_messages: list[discord.Message] = [status_msg]

        try:
            async for event in gw_client.stream_message(
                channel_id=channel_id_str,
                content=user_text,
                attachments=attachments,
            ):
                if cancel_event.is_set():
                    raise asyncio.CancelledError("User cancelled")

                event_type = event.get("type")

                if event_type == "chunk":
                    accumulated += event.get("content", "")

                    # Edit current message periodically
                    now = asyncio.get_event_loop().time()
                    if now - last_edit >= STREAM_EDIT_INTERVAL:
                        # If accumulated content exceeds limit, finalize current
                        # message and start a new one
                        if len(accumulated) > STREAM_MSG_LIMIT:
                            # Find a good split point
                            split_at = accumulated.rfind("\n\n", 0, STREAM_MSG_LIMIT)
                            if split_at <= 0:
                                split_at = accumulated.rfind("\n", 0, STREAM_MSG_LIMIT)
                            if split_at <= 0:
                                split_at = STREAM_MSG_LIMIT

                            finalized = accumulated[:split_at]
                            accumulated = accumulated[split_at:].lstrip("\n")

                            try:
                                await sent_messages[-1].edit(content=finalized)
                            except discord.HTTPException:
                                pass
                            status_msg = await channel.send("*...*")
                            sent_messages.append(status_msg)
                        else:
                            display = accumulated + " \u23f3"  # hourglass
                            # Truncate display for Discord limit
                            if len(display) > MAX_DISCORD_LEN:
                                display = display[:SAFE_LEN] + "..."
                            try:
                                await sent_messages[-1].edit(content=display)
                            except discord.HTTPException:
                                pass
                        last_edit = now

                elif event_type == "response":
                    # Final response — use the complete text
                    final_text = event.get("content", accumulated)

                    # Send remaining content as final message(s)
                    # Delete the streaming status message and send clean final output
                    for msg in sent_messages:
                        try:
                            await msg.delete()
                        except discord.HTTPException:
                            pass

                    for chunk in split_message(final_text):
                        await channel.send(chunk)

                    return final_text

        except asyncio.CancelledError:
            # Clean up status message on cancel
            for msg in sent_messages:
                try:
                    await msg.edit(content="*Cancelled.*")
                except discord.HTTPException:
                    pass
            return None
        except ContextTooLargeError:
            raise  # let caller handle retry
        except (TimeoutError, RuntimeError) as e:
            for msg in sent_messages:
                try:
                    await msg.edit(content=f"*Error: {e}*")
                except discord.HTTPException:
                    pass
            raise

        return accumulated or None

    # -------------------------------------------------------------------
    # Direct CLI fallback with heartbeat status updates
    # -------------------------------------------------------------------

    async def _direct_cli_with_heartbeat(
        channel: discord.TextChannel,
        user_text: str,
        channel_id_str: str,
        cancel_event: asyncio.Event,
    ) -> str | None:
        """Invoke Claude CLI directly with periodic heartbeat messages."""
        append_prompt = _get_context(config)
        status_msg = await channel.send("*processing...*")
        start = asyncio.get_event_loop().time()

        # Run bridge.invoke in a background task so we can update status
        invoke_task = asyncio.create_task(bridge.invoke(
            message=user_text,
            channel_id=channel_id_str,
            append_prompt=append_prompt,
        ))

        try:
            while not invoke_task.done():
                # Check cancel
                if cancel_event.is_set():
                    invoke_task.cancel()
                    try:
                        await status_msg.edit(content="*Cancelled.*")
                    except discord.HTTPException:
                        pass
                    return None

                # Wait a bit, then update heartbeat
                try:
                    await asyncio.wait_for(asyncio.shield(invoke_task), timeout=15)
                except asyncio.TimeoutError:
                    pass  # not done yet — update heartbeat

                if not invoke_task.done():
                    elapsed = asyncio.get_event_loop().time() - start
                    minutes = int(elapsed) // 60
                    seconds = int(elapsed) % 60
                    if minutes:
                        time_str = f"{minutes}m {seconds}s"
                    else:
                        time_str = f"{seconds}s"
                    try:
                        await status_msg.edit(content=f"*still processing... ({time_str})*")
                    except discord.HTTPException:
                        pass

            response = invoke_task.result()

            # Delete status message and send response
            try:
                await status_msg.delete()
            except discord.HTTPException:
                pass

            for chunk in split_message(response):
                await channel.send(chunk)

            return response

        except asyncio.CancelledError:
            invoke_task.cancel()
            try:
                await status_msg.edit(content="*Cancelled.*")
            except discord.HTTPException:
                pass
            return None

    # -------------------------------------------------------------------
    # In-process heartbeat
    # -------------------------------------------------------------------

    def _build_heartbeat_prompt(is_full_scan: bool) -> str:
        """Build the prompt injected for a heartbeat cycle."""
        now = datetime.now(TZ)
        scan_type = "full scan" if is_full_scan else "lightweight"
        heartbeat_path = Path(config.paths.project_dir) / "HEARTBEAT.md"

        # Detect special review windows (full scan only)
        review_type = None
        time_budget = "2-3 minutes"

        if is_full_scan:
            # Monthly: first weekday of month, 14:00-16:00
            is_month_start = now.day <= 3 and now.weekday() < 5
            if is_month_start and 14 <= now.hour < 16:
                review_type = "monthly"
                time_budget = "15 minutes"
            # Weekly: Sunday 15:00-17:00
            elif now.weekday() == 6 and 15 <= now.hour < 17:
                review_type = "weekly"
                time_budget = "10 minutes"

        parts = [
            f"[HEARTBEAT — {scan_type}]",
            f"Read {heartbeat_path} and execute the checks for this scan tier.",
            f"Scan type: {scan_type}",
            f"Current time: {now.strftime('%Y-%m-%d %H:%M %Z')}",
        ]

        if review_type:
            proposals_dir = Path(config.paths.project_dir) / "proposals"
            parts.append(f"Review type: {review_type}")
            parts.append(
                f"This is a {review_type} review cycle. Follow the "
                f"Self-Improvement Protocol in HEARTBEAT.md for the "
                f"{review_type} review checklist."
            )
            parts.append(f"Proposals directory: {proposals_dir}")

        parts.append("")
        parts.append("Response rules:")
        if review_type:
            parts.append(
                "- ALWAYS post a review summary to Discord (never silent "
                "on review cycles)."
            )
            parts.append(
                "- Write the full review note to the Obsidian vault as "
                "described in the Review Summary Format section."
            )
        else:
            parts.append("- If nothing actionable, respond with EXACTLY: [heartbeat ok]")
        parts.append("- If actionable items found, respond with a concise report.")
        parts.append("- Do NOT post to Discord yourself — the bot handles output routing.")
        parts.append(f"- Keep total execution under {time_budget}.")

        return "\n".join(parts)

    async def _heartbeat_cli_invoke(prompt: str, channel_id_str: str) -> str | None:
        """Invoke Claude CLI for a heartbeat cycle. Returns response text."""
        append_prompt = _get_context(config)
        try:
            response = await bridge.invoke(
                message=prompt,
                channel_id=channel_id_str,
                append_prompt=append_prompt,
                priority=True,  # shares user session via --resume
            )
            return response
        except (TimeoutError, RuntimeError, ContextTooLargeError) as e:
            logger.warning("Heartbeat CLI invoke failed: %s", e)
            return None

    def _in_active_hours() -> bool:
        """Check if current time is within configured active hours."""
        now = datetime.now(TZ)
        hb_cfg = config.heartbeat.in_process
        try:
            start_h, start_m = map(int, hb_cfg.active_hours_start.split(":"))
            end_h, end_m = map(int, hb_cfg.active_hours_end.split(":"))
        except (ValueError, AttributeError):
            return True  # default to active if parsing fails
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        return start_minutes <= current_minutes < end_minutes

    async def _heartbeat_loop() -> None:
        """Background heartbeat loop — runs inside the bot's event loop."""
        nonlocal _heartbeat_count

        hb_cfg = config.heartbeat.in_process
        interval = hb_cfg.interval_minutes * 60
        full_scan_every = max(1, hb_cfg.full_scan_interval_minutes // hb_cfg.interval_minutes)
        quiet_period = hb_cfg.quiet_after_message_minutes * 60
        channel_id = config.discord.channel_id
        channel_id_str = str(channel_id)

        # Wait one full interval before first heartbeat
        logger.info(
            "Heartbeat loop started — interval=%dm, full_scan_every=%d cycles, quiet=%dm",
            hb_cfg.interval_minutes, full_scan_every, hb_cfg.quiet_after_message_minutes,
        )
        await asyncio.sleep(interval)

        while True:
            try:
                # Check active hours
                if not _in_active_hours():
                    logger.debug("Heartbeat skipped — outside active hours")
                    await asyncio.sleep(interval)
                    continue

                # Check quiet period
                now_mono = time.monotonic()
                if _last_user_message_time > 0 and (now_mono - _last_user_message_time) < quiet_period:
                    logger.debug("Heartbeat skipped — quiet period (user messaged recently)")
                    await asyncio.sleep(interval)
                    continue

                # Determine scan type
                _heartbeat_count += 1
                is_full_scan = (_heartbeat_count % full_scan_every) == 0

                scan_label = "full scan" if is_full_scan else "lightweight"
                logger.info("Heartbeat cycle #%d (%s)", _heartbeat_count, scan_label)

                prompt = _build_heartbeat_prompt(is_full_scan)

                # Inject into the per-channel queue system
                await _inject_heartbeat(channel_id, prompt)

            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                return
            except Exception:
                logger.exception("Heartbeat loop error — will retry next cycle")

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                return

    async def _inject_heartbeat(channel_id: int, prompt: str) -> None:
        """Inject a heartbeat into the message processing pipeline."""
        channel_id_str = str(channel_id)
        task = _active_tasks.get(channel_id)

        if task and not task.done():
            # Channel is busy — queue the heartbeat
            queue = _get_queue(channel_id)
            try:
                queue.put_nowait({
                    "author": "heartbeat",
                    "user_text": prompt,
                    "attachments": [],
                })
                logger.debug("Heartbeat queued (channel busy)")
            except asyncio.QueueFull:
                logger.debug("Heartbeat skipped — queue full")
        else:
            # Channel idle — process directly
            try:
                channel = await client.fetch_channel(channel_id)
                _start_processing(channel, channel_id, "heartbeat", prompt, [])
            except Exception:
                logger.warning("Failed to inject heartbeat — could not fetch channel")

    # -------------------------------------------------------------------
    # Background message processor
    # -------------------------------------------------------------------

    async def _process_message(
        channel: discord.TextChannel,
        channel_id: int,
        author: str,
        user_text: str,
        attachments: list[dict],
    ) -> None:
        """Process a single message in the background. Handles retries and errors."""
        channel_id_str = str(channel_id)
        is_heartbeat = (author == "heartbeat")

        cancel_event = _get_cancel_event(channel_id)
        _task_start_times[channel_id] = asyncio.get_event_loop().time()

        response: str | None = None
        try:
            if is_heartbeat:
                # Heartbeat path — no status messages, no streaming
                response = await _heartbeat_cli_invoke(user_text, channel_id_str)

                if response:
                    stripped = response.strip()
                    is_silent = "[heartbeat ok]" in stripped.lower()

                    # Log ALL heartbeat output to Obsidian vault
                    _log_heartbeat_to_vault(response, is_silent)

                    if is_silent:
                        logger.info("Heartbeat: ok (silent)")
                    else:
                        # Actionable — post to Discord with emoji indicator
                        emoji = config.heartbeat.in_process.emoji_indicator
                        first_msg = None
                        for chunk in split_message(response):
                            msg = await channel.send(chunk)
                            if first_msg is None:
                                first_msg = msg
                        if first_msg:
                            try:
                                await first_msg.add_reaction(emoji)
                            except discord.HTTPException:
                                pass
                        logger.info("Heartbeat: actionable output posted (%d chars)", len(response))
                        # Log actionable heartbeats to daily log
                        _log_conversation(config, "heartbeat", "(heartbeat cycle)", [], response)
                else:
                    logger.warning("Heartbeat: no response from CLI")
                return  # skip the finally log for heartbeats (logged above if actionable)

            # --- Normal user message path ---
            cancel_event.clear()

            if gw_client and gw_client.connected:
                response = await _stream_gateway_response(
                    channel, channel_id_str, user_text,
                    attachments if attachments else None, cancel_event,
                )
            else:
                if attachments:
                    logger.info("Attachments dropped — gateway unavailable")
                response = await _direct_cli_with_heartbeat(
                    channel, user_text, channel_id_str, cancel_event,
                )

        except ContextTooLargeError:
            logger.warning("Context too large — clearing session and retrying")
            if gw_client:
                gw_client._sessions.pop(channel_id_str, None)
                gw_client._save_sessions()
            await channel.send("Session context was too large — starting fresh.")
            # Retry once with clean session
            try:
                if gw_client and gw_client.connected:
                    response = await _stream_gateway_response(
                        channel, channel_id_str, user_text,
                        attachments if attachments else None, cancel_event,
                    )
                else:
                    append_prompt = _get_context(config)
                    response = await bridge.invoke(
                        message=user_text,
                        channel_id=channel_id_str,
                        append_prompt=append_prompt,
                    )
                    if response:
                        for chunk in split_message(response):
                            await channel.send(chunk)
            except Exception:
                logger.exception("Retry after context-too-large also failed")
                await channel.send("Retry also failed. Try again in a moment.")

        except TimeoutError:
            if not is_heartbeat:
                await channel.send(
                    "Timed out waiting for Claude Code. Try again or simplify the request."
                )
        except RuntimeError as e:
            if not is_heartbeat:
                logger.exception("Claude Code error")
                await channel.send(f"Error from Claude Code: {e}")
            else:
                logger.warning("Heartbeat runtime error: %s", e)
        except asyncio.CancelledError:
            logger.info("Task cancelled for channel %d", channel_id)
        except Exception:
            logger.exception("Unexpected error processing message")
            if not is_heartbeat:
                await channel.send("Something went wrong. Check the logs for details.")
        finally:
            _task_start_times.pop(channel_id, None)
            if not is_heartbeat:
                _log_conversation(config, author, user_text, attachments, response)

    # -------------------------------------------------------------------
    # Task lifecycle — start, complete, drain queue
    # -------------------------------------------------------------------

    def _start_processing(
        channel: discord.TextChannel,
        channel_id: int,
        author: str,
        user_text: str,
        attachments: list[dict],
    ) -> None:
        """Spawn a background task to process a message."""
        task = asyncio.create_task(
            _process_message(channel, channel_id, author, user_text, attachments)
        )
        _active_tasks[channel_id] = task
        task.add_done_callback(lambda t: _on_task_done(channel, channel_id, t))

    def _on_task_done(
        channel: discord.TextChannel,
        channel_id: int,
        task: asyncio.Task,
    ) -> None:
        """Callback when a processing task finishes — drain queue if needed."""
        _active_tasks.pop(channel_id, None)

        # Check for exception we didn't handle
        if not task.cancelled():
            exc = task.exception()
            if exc:
                logger.error("Unhandled exception in message task: %s", exc)

        # Drain next message from queue
        queue = _message_queues.get(channel_id)
        if queue and not queue.empty():
            try:
                next_item = queue.get_nowait()
                _start_processing(
                    channel, channel_id,
                    next_item["author"],
                    next_item["user_text"],
                    next_item["attachments"],
                )
            except asyncio.QueueEmpty:
                pass

    # -------------------------------------------------------------------
    # on_message — dispatch to background tasks
    # -------------------------------------------------------------------

    @client.event
    async def on_message(message: discord.Message) -> None:
        nonlocal _last_user_message_time

        if message.author == client.user:
            return
        if message.channel.id != config.discord.channel_id:
            return
        if message.guild and message.guild.id != config.discord.guild_id:
            return

        # Track last user message time for heartbeat quiet period
        _last_user_message_time = time.monotonic()

        user_text = message.content.strip()

        # Notes mode: save images to Inbound Notes for the notes-inbound skill
        notes_mode = _is_notes_request(user_text) and bool(message.attachments)

        if notes_mode:
            saved_files = []
            for att in message.attachments[:MAX_ATTACHMENTS]:
                if att.size > MAX_FILE_SIZE:
                    continue
                try:
                    data = await att.read()
                except Exception:
                    continue
                img_type = _detect_image_type(data)
                if img_type:
                    ext = {
                        "image/jpeg": ".jpg",
                        "image/png": ".png",
                        "image/gif": ".gif",
                        "image/webp": ".webp",
                    }.get(img_type, ".jpg")
                    ts_name = datetime.now(TZ).strftime("%Y%m%d_%H%M%S") + ext
                    saved = _save_attachment(ts_name, data, dest_dir=_INBOUND_NOTES_DIR)
                    if saved:
                        saved_files.append(saved)
            if saved_files:
                paths = ", ".join(saved_files)
                user_text = (
                    f"[Attachments saved to Inbound Notes: {paths}] "
                    "Process these notes using the notes-inbound skill.\n\n"
                    + user_text
                )
            attachments: list[dict] = []  # don't send inline — skill reads from disk
        else:
            attachments = await _download_attachments(message.attachments)

        if not user_text and not attachments:
            return

        channel_id = message.channel.id

        # --- Synchronous commands (not queued) ---

        if user_text == "!restart":
            logger.info("Restart requested by %s", message.author)
            await message.channel.send("Restarting. Back in ~10 seconds.")
            await _shutdown()
            return

        if user_text == "!reload":
            logger.info("Reload requested by %s", message.author)
            _refresh_context(config)
            await message.channel.send("Context cache rebuilt.")
            return

        if user_text == "!cancel":
            cancel_event = _get_cancel_event(channel_id)
            cancel_event.set()
            # Also send gateway-level cancel
            if gw_client and gw_client.connected:
                await gw_client.cancel_session(str(channel_id))
            # Cancel the asyncio task
            task = _active_tasks.get(channel_id)
            if task and not task.done():
                task.cancel()
            # Clear the queue
            queue = _message_queues.get(channel_id)
            if queue:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            await message.add_reaction("\u2705")  # checkmark
            return

        if user_text == "!status":
            task = _active_tasks.get(channel_id)
            queue = _message_queues.get(channel_id)
            queue_depth = queue.qsize() if queue else 0
            if task and not task.done():
                start_time = _task_start_times.get(channel_id)
                if start_time:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    minutes = int(elapsed) // 60
                    seconds = int(elapsed) % 60
                    time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
                else:
                    time_str = "unknown"
                await message.channel.send(
                    f"Running ({time_str}). {queue_depth} queued."
                )
            else:
                await message.channel.send("Idle.")
            return

        # --- Regular messages —  dispatch to background ---

        logger.info("Message from %s: %s%s", message.author, user_text[:100],
                     f" (+{len(attachments)} attachments)" if attachments else "")

        task = _active_tasks.get(channel_id)
        if task and not task.done():
            # Already processing — queue this message
            queue = _get_queue(channel_id)
            try:
                queue.put_nowait({
                    "author": str(message.author),
                    "user_text": user_text,
                    "attachments": attachments,
                })
                await message.add_reaction("\U0001f440")  # eyes
            except asyncio.QueueFull:
                await message.channel.send(
                    "Queue is full (5 messages). Wait for the current task to finish."
                )
        else:
            _start_processing(
                message.channel, channel_id,
                str(message.author), user_text, attachments,
            )

    return client


def _get_context(config: Config) -> str | None:
    """Return cached context for message handling.

    Uses in-memory cache (no disk reads per message).
    Falls back to rebuilding if cache is somehow empty.
    Appends a fresh date/time line on every call so it's never stale.
    """
    global _cached_context
    context = _cached_context
    if not context:
        context = _refresh_context(config)
        if not context or not context.strip():
            return None

    now = datetime.now(TZ)
    date_line = f"\n\n## Current Date\n\nToday is {now.strftime('%A')}, {now.strftime('%Y-%m-%d')}. Current time: {now.strftime('%H:%M')}."
    return context + date_line


# ---------------------------------------------------------------------------
# Context file watcher — watches SOUL.md, STYLE.md, SKILL.md, IDENTITY.md, USER.md
# ---------------------------------------------------------------------------

# Files that trigger a context cache refresh when modified
_CONTEXT_WATCH_PATTERNS = {"SOUL.md", "STYLE.md", "SKILL.md", "IDENTITY.md", "USER.md"}


def _start_context_watcher(client: discord.Client) -> None:
    """Start a watchdog observer for context-relevant files.

    Watches skills dir + project root for changes to SOUL.md, STYLE.md,
    SKILL.md, IDENTITY.md, USER.md. Triggers context cache rebuild on changes.
    """
    try:
        from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
        from watchdog.observers import Observer
    except ImportError:
        logger.debug("watchdog not available for context watcher")
        return

    config: Config = client.config  # type: ignore[attr-defined]
    loop = asyncio.get_event_loop()

    class ContextFileHandler(FileSystemEventHandler):
        def __init__(self) -> None:
            self._debounce_timer: asyncio.TimerHandle | None = None

        def _should_handle(self, path: str) -> bool:
            name = Path(path).name
            return name in _CONTEXT_WATCH_PATTERNS

        def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
            if event.is_directory or not self._should_handle(event.src_path):
                return
            self._schedule_refresh(event.src_path)

        def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
            if event.is_directory or not self._should_handle(event.src_path):
                return
            self._schedule_refresh(event.src_path)

        def on_deleted(self, event: FileDeletedEvent) -> None:  # type: ignore[override]
            if event.is_directory or not self._should_handle(event.src_path):
                return
            self._schedule_refresh(event.src_path)

        def _schedule_refresh(self, path: str) -> None:
            """Debounced context refresh — wait 2s after last change."""
            logger.info("Context file changed: %s — scheduling cache rebuild", Path(path).name)
            loop.call_soon_threadsafe(self._do_schedule)

        def _do_schedule(self) -> None:
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = loop.call_later(2.0, self._do_refresh)

        def _do_refresh(self) -> None:
            _refresh_context(config)
            logger.info("Context cache rebuilt due to file change")

    handler = ContextFileHandler()
    observer = Observer()

    # Watch skills directory (recursive — catches skills/*/SKILL.md)
    skills_dir = Path(config.paths.skills_dir)
    if skills_dir.is_dir():
        observer.schedule(handler, str(skills_dir), recursive=True)

    # Watch project root for SOUL.md, STYLE.md, IDENTITY.md, USER.md
    project_dir = Path(config.paths.project_dir)
    if project_dir.is_dir():
        observer.schedule(handler, str(project_dir), recursive=False)

    observer.daemon = True
    observer.start()
    logger.info("Context file watcher started (skills + identity)")

    # Store reference for cleanup — append to existing observer list
    existing = getattr(client, "_context_observer", None)
    if existing:
        try:
            existing.stop()
        except Exception:
            pass
    client._context_observer = observer  # type: ignore[attr-defined]


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

        # Schedules run via launchd — no in-process scheduler needed.
        # Edit config/schedules.yaml and run scripts/schedule-sync.py to sync.

        # File watcher for vault/config files
        try:
            from .file_watcher import start_file_watcher
            start_file_watcher(client)
            logger.info("File watcher started")
        except ImportError:
            logger.debug("File watcher not yet available")

        # Context file watcher for SKILL.md, IDENTITY.md, USER.md
        _start_context_watcher(client)

        # Register SIGTERM handler for graceful shutdown (launchd sends SIGTERM)
        loop = asyncio.get_running_loop()
        shutdown = getattr(client, "_shutdown", None)
        if shutdown:
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(shutdown()))

    client.setup_hook = setup_hook  # type: ignore[method-assign]

    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
