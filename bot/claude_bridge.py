"""Invoke Claude Code CLI and parse responses."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    session_id: str
    last_used: float  # time.monotonic()
    message_count: int = 0


class ClaudeBridge:
    """Manages Claude Code CLI invocations with session tracking and concurrency control."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._semaphore = asyncio.Semaphore(1)
        self._sessions: dict[str, SessionInfo] = {}  # channel_id -> SessionInfo

    def _get_session(self, channel_id: str) -> SessionInfo:
        """Get or create a session for a channel, expiring stale sessions."""
        now = time.monotonic()
        expiry = self.config.claude.session_expiry_minutes * 60

        info = self._sessions.get(channel_id)
        if info and (now - info.last_used) < expiry:
            info.last_used = now
            return info

        # Create new session
        session_id = str(uuid.uuid4())
        info = SessionInfo(session_id=session_id, last_used=now)
        self._sessions[channel_id] = info
        return info

    def _build_command(
        self,
        session: SessionInfo,
        append_prompt: str | None = None,
    ) -> list[str]:
        """Build the claude CLI command."""
        cmd = [
            self.config.claude.path,
            "--print",
            "--output-format", "json",
            "--add-dir", self.config.vault.path,
        ]

        if session.message_count == 0:
            # First message: create a new session with specific ID
            cmd.extend(["--session-id", session.session_id])
        else:
            # Follow-up: resume the existing session
            cmd.extend(["--resume", session.session_id])

        if append_prompt:
            cmd.extend(["--append-system-prompt", append_prompt])
        return cmd

    @staticmethod
    def _extract_response(stdout: bytes) -> str:
        """Extract the assistant's response text from Claude Code JSON output."""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # Fall back to raw text if not valid JSON
            return stdout.decode("utf-8", errors="replace").strip()

        # Claude Code --output-format json returns:
        # {"type": "result", "result": "...", ...}
        # or a list of content blocks
        if isinstance(data, dict):
            # Direct result string
            if "result" in data:
                return data["result"]
            # Content blocks format
            if "content" in data:
                parts = []
                for block in data["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block["text"])
                    elif isinstance(block, str):
                        parts.append(block)
                return "\n".join(parts)

        return stdout.decode("utf-8", errors="replace").strip()

    async def invoke(
        self,
        message: str,
        channel_id: str = "default",
        append_prompt: str | None = None,
        priority: bool = True,
    ) -> str:
        """Send a message to Claude Code and return the response.

        Args:
            message: The user message to send.
            channel_id: Channel identifier for session tracking.
            append_prompt: Additional system prompt context (memory, skills).
            priority: If True, acquires semaphore immediately (user messages).

        Returns:
            The assistant's response text.

        Raises:
            TimeoutError: If Claude Code doesn't respond within timeout.
            RuntimeError: If Claude Code process fails.
        """
        session = self._get_session(channel_id)
        cmd = self._build_command(session, append_prompt)

        logger.info(
            "Invoking Claude Code — session=%s channel=%s msg_count=%d msg_len=%d",
            session.session_id[:8],
            channel_id,
            session.message_count,
            len(message),
        )

        async with self._semaphore:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.paths.project_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=message.encode("utf-8")),
                    timeout=self.config.claude.timeout_seconds,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise TimeoutError(
                    f"Claude Code timed out after {self.config.claude.timeout_seconds}s"
                )

        if proc.returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace").strip()
            logger.error("Claude Code failed (rc=%d): %s", proc.returncode, err_text)
            # If session conflict, invalidate and retry with fresh session
            if "already in use" in err_text:
                logger.info("Session conflict — creating fresh session for channel %s", channel_id)
                del self._sessions[channel_id]
                return await self.invoke(message, channel_id, append_prompt, priority)
            raise RuntimeError(f"Claude Code exited with code {proc.returncode}: {err_text}")

        session.message_count += 1
        response = self._extract_response(stdout)
        logger.info("Claude Code responded — %d chars", len(response))
        return response

    async def invoke_scheduled(
        self,
        prompt: str,
        append_prompt: str | None = None,
    ) -> str:
        """Invoke Claude Code for a scheduled task (lower priority, dedicated session)."""
        return await self.invoke(
            message=prompt,
            channel_id=f"scheduled-{uuid.uuid4().hex[:8]}",
            append_prompt=append_prompt,
            priority=False,
        )
