"""Gateway entry point — starts the WebSocket server and manages lifecycle."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure project root is importable
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from bot.config import Config
from bot.context import build_context, write_cache

from .claude_pool import ClaudePool
from .router import Router
from .server import GatewayServer
from .sessions import SessionManager
from .tcc import run_all_probes

logger = logging.getLogger(__name__)
TZ = ZoneInfo("America/Chicago")


class Gateway:
    """Main gateway process — owns all subsystems."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._session_mgr: SessionManager | None = None
        self._claude_pool: ClaudePool | None = None
        self._router: Router | None = None
        self._server: GatewayServer | None = None
        self._context_cache: str | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Initialize all subsystems and start serving."""
        logger.info("Gateway starting...")

        # Build context cache
        self._context_cache = build_context(self.config)
        write_cache(self.config, self._context_cache)
        logger.info("Context cache built (%d chars)", len(self._context_cache))

        # TCC permission probes
        run_all_probes(self.config.paths.project_dir)

        # Initialize session manager
        db_path = Path(self.config.paths.data_dir) / "gateway.db"
        self._session_mgr = SessionManager(db_path)

        # Reap orphan claude processes from previous run
        active = self._session_mgr.get_active_sessions()
        orphan_pids = {s.claude_pid for s in active if s.claude_pid}
        if orphan_pids:
            # Clear stale PIDs from sessions before reaping
            for s in active:
                if s.claude_pid:
                    self._session_mgr.set_claude_info(s.id, claude_session_id=s.claude_session_id, claude_pid=None)

        # Build MCP config path
        mcp_config_path = self._build_mcp_config()

        # Collect MCP env overrides
        env_overrides: dict[str, str] = {}
        for srv in self.config.mcp.servers:
            env_overrides.update(srv.env)

        # Initialize claude process pool
        self._claude_pool = ClaudePool(
            claude_path=self.config.claude.path,
            project_dir=self.config.paths.project_dir,
            vault_path=self.config.vault.path,
            mcp_config_path=mcp_config_path,
            max_processes=self.config.gateway.max_claude_processes,
            hang_timeout=self.config.gateway.claude_hang_timeout_seconds,
            env_overrides=env_overrides,
        )

        # Reap orphans
        if orphan_pids:
            killed = await self._claude_pool.reap_orphans(orphan_pids)
            if killed:
                logger.info("Reaped %d orphan claude processes", killed)

        # Initialize router
        self._router = Router(
            session_mgr=self._session_mgr,
            claude_pool=self._claude_pool,
            auth_token=self.config.gateway.auth_token,
            context_fn=lambda: self._context_cache,
        )

        # Start WebSocket server
        self._server = GatewayServer(
            router=self._router,
            host=self.config.gateway.host,
            port=self.config.gateway.port,
        )
        await self._server.start()

        # Register signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(self.shutdown()))

        # Start session expiry task
        asyncio.create_task(self._session_expiry_loop())

        # Write state
        self._update_state("gateway_started_at")
        logger.info("Gateway ready — listening on ws://%s:%d",
                     self.config.gateway.host, self.config.gateway.port)

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def shutdown(self) -> None:
        """Graceful shutdown — drain connections, kill processes, save state."""
        if self._shutdown_event.is_set():
            return
        logger.info("Gateway shutting down...")

        # Stop WebSocket server (stops accepting new connections)
        if self._server:
            await self._server.stop()

        # Kill all claude processes
        if self._claude_pool:
            await self._claude_pool.kill_all()

        # Close session database
        if self._session_mgr:
            self._session_mgr.close()

        self._update_state("gateway_stopped_at")
        logger.info("Gateway shutdown complete")
        self._shutdown_event.set()

    async def _session_expiry_loop(self) -> None:
        """Periodically expire idle and old sessions."""
        idle_timeout = self.config.gateway.session_idle_timeout_minutes * 60
        expiry_timeout = self.config.gateway.session_expiry_minutes * 60

        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)  # Check every minute
            try:
                # Expire idle sessions and kill their claude processes
                idle = self._session_mgr.expire_idle_sessions(idle_timeout)
                for s in idle:
                    await self._claude_pool.kill_session(s.id)

                # Expire old sessions
                self._session_mgr.expire_old_sessions(expiry_timeout)
            except Exception:
                logger.exception("Error in session expiry loop")

    def _build_mcp_config(self) -> str | None:
        """Write MCP config JSON and return the path."""
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
        return str(config_path)

    def _update_state(self, event: str) -> None:
        """Write a lifecycle event to data/state.json."""
        state_path = Path(self.config.paths.data_dir) / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            state = {}
        state[event] = datetime.now(TZ).isoformat()
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Start the gateway process."""
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

    gateway = Gateway(config)
    asyncio.run(gateway.start())


if __name__ == "__main__":
    main()
