"""Claude CLI process pool — spawn, stream, cancel, and reap claude subprocesses.

Each session gets a long-running claude process using bidirectional JSON streaming:
  claude --print --input-format=stream-json --output-format=stream-json
         --verbose --dangerously-skip-permissions

Messages are sent as JSON on stdin, responses stream back as JSON events on stdout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Claude process wrapper
# ---------------------------------------------------------------------------


@dataclass
class ClaudeProcess:
    """A long-running claude CLI subprocess."""

    session_id: str
    claude_session_id: str  # Claude's internal session UUID
    proc: asyncio.subprocess.Process
    started_at: float = field(default_factory=time.time)
    last_output_at: float = field(default_factory=time.time)
    message_count: int = 0
    _initialized: bool = False

    _stderr_task: asyncio.Task | None = None

    @property
    def pid(self) -> int | None:
        return self.proc.pid

    @property
    def alive(self) -> bool:
        return self.proc.returncode is None

    def start_stderr_reader(self) -> None:
        """Start a background task to log stderr from the claude process."""
        if self.proc.stderr:
            self._stderr_task = asyncio.create_task(self._read_stderr())

    async def _read_stderr(self) -> None:
        """Read and log stderr lines from the claude process."""
        try:
            while True:
                line = await self.proc.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    logger.warning("Claude pid=%s stderr: %s", self.pid, text[:500])
        except Exception:
            pass

    def _parse_init(self, line: str) -> str | None:
        """Parse the init message from claude, extract session_id. Returns session_id or None."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if data.get("type") == "system" and data.get("subtype") == "init":
            return data.get("session_id")
        return None

    async def send_message(self, content: str) -> None:
        """Send a user message to the claude process via stdin.

        Uses the Claude CLI stream-json input format:
        {"type":"user","message":{"role":"user","content":[{"type":"text","text":"..."}]}}
        """
        if not self.alive:
            raise RuntimeError(f"Claude process {self.pid} is not alive")

        msg = json.dumps({
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": content}],
            },
        })
        self.proc.stdin.write((msg + "\n").encode("utf-8"))
        await self.proc.stdin.drain()
        self.message_count += 1
        logger.debug("Sent message to claude pid=%s (%d chars)", self.pid, len(content))

    async def read_response(self, hang_timeout: int = 120) -> AsyncIterator[dict]:
        """Read streaming JSON events from claude stdout until a result event.

        Yields parsed JSON dicts. The last yielded dict will have type="result".
        Raises TimeoutError if no output received within hang_timeout seconds.
        """
        while True:
            try:
                line = await asyncio.wait_for(
                    self.proc.stdout.readline(),
                    timeout=hang_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Claude process pid=%s hung (no output for %ds)",
                    self.pid, hang_timeout,
                )
                raise TimeoutError(
                    f"Claude process hung — no output for {hang_timeout}s"
                )

            if not line:
                # EOF — process died
                logger.warning("Claude process pid=%s EOF", self.pid)
                raise RuntimeError("Claude process terminated unexpectedly")

            self.last_output_at = time.time()
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                logger.debug("Non-JSON line from claude: %s", text[:200])
                continue

            # Handle init message on first response
            if not self._initialized and data.get("type") == "system":
                sid = data.get("session_id")
                if sid:
                    self.claude_session_id = sid
                    self._initialized = True
                    logger.info(
                        "Claude process pid=%s initialized (session=%s)",
                        self.pid, sid[:8],
                    )
                continue

            yield data

            # Result event marks end of this response
            if data.get("type") == "result":
                return

    async def cancel(self) -> None:
        """Cancel the current operation by sending SIGINT."""
        if self.alive and self.pid:
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGINT)
                logger.info("Sent SIGINT to claude pgid=%s", self.pid)
            except (ProcessLookupError, OSError):
                pass

    async def kill(self) -> None:
        """Kill the claude process."""
        if self.alive:
            try:
                if self.pid:
                    os.killpg(os.getpgid(self.pid), signal.SIGTERM)
                else:
                    self.proc.terminate()
            except (ProcessLookupError, OSError):
                pass
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()
            logger.info("Killed claude process pid=%s", self.pid)


# ---------------------------------------------------------------------------
# Process pool
# ---------------------------------------------------------------------------


class ClaudePool:
    """Manages a pool of long-running claude CLI processes."""

    def __init__(
        self,
        claude_path: str,
        project_dir: str,
        vault_path: str,
        mcp_config_path: str | None = None,
        max_processes: int = 3,
        hang_timeout: int = 120,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        self._claude_path = claude_path
        self._project_dir = project_dir
        self._vault_path = vault_path
        self._mcp_config_path = mcp_config_path
        self._max_processes = max_processes
        self._hang_timeout = hang_timeout
        self._env_overrides = env_overrides or {}
        self._processes: dict[str, ClaudeProcess] = {}  # session_id -> ClaudeProcess

    @property
    def active_count(self) -> int:
        return sum(1 for p in self._processes.values() if p.alive)

    def get_process(self, session_id: str) -> ClaudeProcess | None:
        """Get the claude process for a session, or None."""
        proc = self._processes.get(session_id)
        if proc and not proc.alive:
            del self._processes[session_id]
            return None
        return proc

    async def spawn(
        self,
        session_id: str,
        claude_session_id: str | None = None,
        append_prompt: str | None = None,
    ) -> ClaudeProcess:
        """Spawn a new claude CLI process for a session.

        Args:
            session_id: Gateway session ID.
            claude_session_id: Claude's session ID to resume. If None, creates new.
            append_prompt: System prompt to append (context cache).

        Returns:
            The spawned ClaudeProcess.

        Raises:
            RuntimeError: If max processes reached.
        """
        if self.active_count >= self._max_processes:
            raise RuntimeError(
                f"Max claude processes reached ({self._max_processes}). "
                "Try again after an idle session expires."
            )

        # Kill existing process for this session if any
        existing = self._processes.get(session_id)
        if existing and existing.alive:
            await existing.kill()

        cmd = self._build_command(claude_session_id, append_prompt)
        env = self._build_env()

        logger.info(
            "Spawning claude process for session %s (resume=%s)",
            session_id[:8],
            claude_session_id[:8] if claude_session_id else "new",
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._project_dir,
            env=env,
            preexec_fn=os.setpgrp,  # Own process group for clean kill
        )

        cp = ClaudeProcess(
            session_id=session_id,
            claude_session_id=claude_session_id or "",
            proc=proc,
        )
        self._processes[session_id] = cp

        # Note: Claude CLI stream-json mode only emits the init message
        # after receiving the first user message, not at startup.
        # The init message is captured in read_response().
        cp.start_stderr_reader()
        logger.info("Claude process pid=%s spawned", proc.pid)

        return cp

    async def cancel(self, session_id: str) -> None:
        """Cancel the current operation for a session."""
        proc = self.get_process(session_id)
        if proc:
            await proc.cancel()

    async def kill_session(self, session_id: str) -> None:
        """Kill the claude process for a session."""
        proc = self._processes.pop(session_id, None)
        if proc:
            await proc.kill()

    async def kill_all(self) -> None:
        """Kill all claude processes (for shutdown)."""
        tasks = []
        for session_id in list(self._processes):
            proc = self._processes.pop(session_id, None)
            if proc and proc.alive:
                tasks.append(proc.kill())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Killed %d claude processes", len(tasks))

    async def reap_orphans(self, known_pids: set[int]) -> int:
        """Check for stale claude processes from a previous gateway run.

        Args:
            known_pids: Set of PIDs from persisted session data.

        Returns:
            Number of orphans killed.
        """
        killed = 0
        for pid in known_pids:
            try:
                os.kill(pid, 0)  # Check if process exists
                # Process exists — kill it
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    killed += 1
                    logger.info("Killed orphan claude process pid=%d", pid)
                except (ProcessLookupError, OSError):
                    pass
            except (ProcessLookupError, OSError):
                pass  # Process doesn't exist — already gone
        return killed

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _build_command(
        self,
        claude_session_id: str | None = None,
        append_prompt: str | None = None,
    ) -> list[str]:
        cmd = [
            self._claude_path,
            "--print",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--add-dir", self._vault_path,
        ]

        if self._mcp_config_path:
            cmd.extend(["--mcp-config", self._mcp_config_path])

        if claude_session_id:
            cmd.extend(["--resume", claude_session_id])

        if append_prompt:
            cmd.extend(["--append-system-prompt", append_prompt])

        return cmd

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        # Prepend bin/ so claude finds clawcal and other compiled tools
        bin_dir = str(Path(self._project_dir) / "bin")
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin:/bin')}"
        env.update(self._env_overrides)
        return env
