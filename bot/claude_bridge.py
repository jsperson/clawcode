"""Invoke Claude Code CLI and parse responses."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    session_id: str
    last_used: float  # time.time() (wall clock, survives restarts)
    message_count: int = 0


class ClaudeBridge:
    """Manages Claude Code CLI invocations with session tracking and concurrency control."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._semaphore = asyncio.Semaphore(1)
        self._sessions: dict[str, SessionInfo] = {}  # channel_id -> SessionInfo
        self._mcp_config_path: Path | None = self._build_mcp_config()
        self._sessions_path = Path(config.paths.data_dir) / "sessions.json"
        self._load_sessions()

    def _build_mcp_config(self) -> Path | None:
        """Write MCP server config JSON for the Claude CLI --mcp-config flag.

        Returns the path to the written file, or None if no servers configured.
        """
        if not self.config.mcp.servers:
            return None

        mcp_servers = {}
        for srv in self.config.mcp.servers:
            entry: dict = {}
            if srv.transport == "stdio":
                if srv.command:
                    entry["command"] = srv.command
                if srv.args:
                    entry["args"] = srv.args
            else:
                if srv.url:
                    entry["url"] = srv.url
            if srv.env:
                entry["env"] = srv.env
            mcp_servers[srv.name] = entry

        config_data = {"mcpServers": mcp_servers}
        data_dir = Path(self.config.paths.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        config_path = data_dir / ".mcp-config.json"
        config_path.write_text(json.dumps(config_data, indent=2) + "\n")
        logger.info("Wrote MCP config to %s (%d servers)", config_path, len(mcp_servers))
        return config_path

    def _load_sessions(self) -> None:
        """Load persisted sessions from disk, pruning any past the expiry window."""
        if not self._sessions_path.exists():
            return
        try:
            data = json.loads(self._sessions_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load sessions from %s: %s", self._sessions_path, e)
            return

        now = time.time()
        expiry = self.config.claude.session_expiry_minutes * 60
        loaded = 0
        for channel_id, entry in data.items():
            last_used = entry.get("last_used", 0)
            if (now - last_used) < expiry:
                self._sessions[channel_id] = SessionInfo(
                    session_id=entry["session_id"],
                    last_used=last_used,
                    message_count=entry.get("message_count", 0),
                )
                loaded += 1
        logger.info("Loaded %d sessions (%d expired)", loaded, len(data) - loaded)

    def save_sessions(self) -> None:
        """Persist current sessions to disk."""
        data = {}
        for channel_id, info in self._sessions.items():
            data[channel_id] = {
                "session_id": info.session_id,
                "last_used": info.last_used,
                "message_count": info.message_count,
            }
        self._sessions_path.parent.mkdir(parents=True, exist_ok=True)
        self._sessions_path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        logger.info("Saved %d sessions to %s", len(data), self._sessions_path)

    def _get_session(self, channel_id: str) -> SessionInfo:
        """Get or create a session for a channel, expiring stale sessions."""
        now = time.time()
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
            "--dangerously-skip-permissions",
            "--add-dir", self.config.vault.path,
        ]

        if self._mcp_config_path:
            cmd.extend(["--mcp-config", str(self._mcp_config_path)])

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
            env = os.environ.copy()
            # Prepend bin/ so Claude finds clawcal and other compiled tools
            bin_dir = str(Path(self.config.paths.project_dir) / "bin")
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin:/bin')}"
            for server in self.config.mcp.servers:
                env.update(server.env)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.paths.project_dir,
                env=env,
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
