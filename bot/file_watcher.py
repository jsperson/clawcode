"""File watcher — Watchdog-based vault monitoring with debounce and iCloud filtering."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import threading
import time
from pathlib import Path

import discord
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .config import Config, WatchEntry

logger = logging.getLogger(__name__)


class _DebouncedHandler(FileSystemEventHandler):
    """Watchdog handler with debounce, iCloud filtering, and Discord notification."""

    def __init__(
        self,
        client: discord.Client,
        watch: WatchEntry,
        config: Config,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.client = client
        self.watch = watch
        self.config = config
        self.loop = loop
        self._last_event: dict[str, float] = {}  # path -> timestamp
        self._debounce = config.file_watch.debounce_seconds
        self._ignore = config.file_watch.ignore_patterns

    def _should_ignore(self, path: str) -> bool:
        """Check if a file path should be ignored."""
        name = Path(path).name
        for pattern in self._ignore:
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(path, pattern):
                return True
        # Filter iCloud placeholder files
        if name.startswith(".") and name.endswith(".icloud"):
            return True
        return False

    def _is_debounced(self, path: str) -> bool:
        """Check if we've already handled this path recently."""
        now = time.monotonic()
        last = self._last_event.get(path, 0)
        if now - last < self._debounce:
            return True
        self._last_event[path] = now
        return False

    def _is_fully_synced(self, path: str) -> bool:
        """Verify file is fully synced (not an iCloud stub)."""
        p = Path(path)
        if not p.exists():
            return False
        # iCloud stubs are very small and have specific names
        if p.stat().st_size == 0:
            return False
        return True

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self._handle(event.src_path)

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        # Only process modifications if watch is configured for it
        if self.watch.on == "new_file":
            return
        self._handle(event.src_path)

    def _handle(self, path: str) -> None:
        """Process a file event with filtering and debouncing."""
        if self._should_ignore(path):
            return
        if self._is_debounced(path):
            return
        if not self._is_fully_synced(path):
            logger.debug("File not fully synced, skipping: %s", path)
            return

        filename = Path(path).name
        prompt = self.watch.prompt.format(filename=filename, path=path)

        logger.info("File event: %s — %s", self.watch.on, path)

        # Schedule async notification on the bot's event loop
        asyncio.run_coroutine_threadsafe(
            self._notify(filename, prompt),
            self.loop,
        )

    async def _notify(self, filename: str, prompt: str) -> None:
        """Post notification to Discord and optionally invoke Claude."""
        config = self.config
        channel = self.client.get_channel(config.discord.channel_id)
        if not channel:
            logger.error("Cannot find Discord channel for file watcher notification")
            return

        # Always notify
        await channel.send(f"📁 **File detected:** {filename}")

        # If action is "process", also invoke Claude
        if self.watch.action in ("process", "notify"):
            try:
                bridge = self.client.bridge  # type: ignore[attr-defined]
                response = await bridge.invoke_scheduled(prompt=prompt)

                from .main import split_message
                for chunk in split_message(response):
                    await channel.send(chunk)
            except Exception:
                logger.exception("File watcher Claude invocation failed for %s", filename)


def start_file_watcher(client: discord.Client) -> Observer | None:
    """Start watchdog observers for configured watch paths."""
    config: Config = client.config  # type: ignore[attr-defined]

    if not config.file_watch.enabled:
        logger.info("File watcher disabled in config")
        return None

    if not config.file_watch.watches:
        logger.info("No file watches configured")
        return None

    loop = asyncio.get_event_loop()
    observer = Observer()

    for watch in config.file_watch.watches:
        watch_path = Path(watch.path)
        if not watch_path.exists():
            logger.warning("Watch path does not exist: %s", watch_path)
            continue

        handler = _DebouncedHandler(client, watch, config, loop)
        observer.schedule(handler, str(watch_path), recursive=False)
        logger.info("Watching: %s (on=%s)", watch_path, watch.on)

    observer.daemon = True
    observer.start()
    logger.info("File watcher started with %d watches", len(config.file_watch.watches))

    # Store reference for cleanup
    client._file_observer = observer  # type: ignore[attr-defined]
    return observer
