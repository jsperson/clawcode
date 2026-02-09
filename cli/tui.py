"""TUI client — attach to gateway sessions and run claude interactively.

Connects to the gateway WebSocket, lists/creates sessions, then hands off
to `claude --resume` running natively in the terminal. Falls back to
standalone claude if the gateway is unavailable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from websockets.sync.client import ClientConnection

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CLAWCODE_DIR = Path.home() / "clawcode"
CLAUDE_BIN = Path.home() / ".npm-global" / "bin" / "claude"
VAULT = Path.home() / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / "scott"
CONTEXT_CACHE = CLAWCODE_DIR / "data" / "context.cache"
CONFIG_PATH = CLAWCODE_DIR / "config" / "config.yaml"
MCP_CONFIG_PATH = CLAWCODE_DIR / "data" / ".mcp-config.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Read gateway host/port from config.yaml."""
    try:
        import yaml

        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        gw = cfg.get("gateway", {})
        return {
            "host": gw.get("host", "127.0.0.1"),
            "port": gw.get("port", 7429),
        }
    except Exception:
        return {"host": "127.0.0.1", "port": 7429}


def get_token() -> str:
    """Read gateway auth token from .env, falling back to environment."""
    # Load .env if dotenv is available (same as bot/config.py)
    env_path = CLAWCODE_DIR / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            # Parse .env manually — just KEY=VALUE lines
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    v = v.strip()
                    # Strip surrounding quotes (matches python-dotenv behavior)
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                        v = v[1:-1]
                    os.environ.setdefault(k.strip(), v)
    return os.environ.get("GATEWAY_TOKEN", "")


# ---------------------------------------------------------------------------
# Gateway communication
# ---------------------------------------------------------------------------


def gateway_connect(host: str, port: int, token: str) -> tuple[ClientConnection, str] | None:
    """Connect to gateway WebSocket, authenticate, return (ws, client_id).

    Returns None if gateway is unreachable.
    """
    from websockets.sync.client import connect
    from websockets.exceptions import WebSocketException

    uri = f"ws://{host}:{port}"
    try:
        ws = connect(uri, open_timeout=3)
    except (OSError, WebSocketException):
        return None

    # Authenticate
    ws.send(json.dumps({
        "type": "auth",
        "token": token,
        "client_type": "tui",
    }))

    try:
        raw = ws.recv(timeout=5)
    except (TimeoutError, ConnectionError):
        ws.close()
        return None

    data = json.loads(raw)
    if data.get("type") != "auth.ok":
        print(f"Auth failed: {data.get('message', 'unknown error')}", file=sys.stderr)
        ws.close()
        return None

    return ws, data["client_id"]


def list_sessions(ws: ClientConnection) -> list[dict]:
    """Request active/idle sessions from gateway."""
    ws.send(json.dumps({"type": "session.list"}))
    raw = ws.recv(timeout=5)
    data = json.loads(raw)
    if data.get("type") == "session.list.ok":
        return data.get("sessions", [])
    return []


def create_session(ws: ClientConnection) -> str | None:
    """Create a new session, return session_id."""
    ws.send(json.dumps({"type": "session.create", "metadata": {"source": "tui"}}))
    raw = ws.recv(timeout=5)
    data = json.loads(raw)
    if data.get("type") == "session.created":
        return data["session_id"]
    print(f"Failed to create session: {data}", file=sys.stderr)
    return None


def attach_session(ws: ClientConnection, session_id: str) -> dict | None:
    """Attach to a session, return {session_id, claude_session_id} or None."""
    ws.send(json.dumps({"type": "session.attach", "session_id": session_id}))
    raw = ws.recv(timeout=10)
    data = json.loads(raw)
    if data.get("type") == "session.attach.ok":
        return data
    print(f"Failed to attach: {data.get('message', data)}", file=sys.stderr)
    return None


def detach_session(ws: ClientConnection, session_id: str, claude_session_id: str) -> None:
    """Best-effort detach — don't fail if gateway is gone."""
    try:
        ws.send(json.dumps({
            "type": "session.detach",
            "session_id": session_id,
            "claude_session_id": claude_session_id,
        }))
        ws.recv(timeout=3)
    except (OSError, TimeoutError):
        pass


# ---------------------------------------------------------------------------
# Session picker
# ---------------------------------------------------------------------------


def pick_session(sessions: list[dict]) -> str | None:
    """Display numbered list, prompt for choice or 'n' for new. Returns session_id or None for new."""
    if not sessions:
        return None

    from datetime import datetime

    print("\nActive sessions:")
    print("-" * 72)
    for i, s in enumerate(sessions, 1):
        ts = datetime.fromtimestamp(s["last_activity"]).strftime("%H:%M")
        attached = " [attached]" if s.get("attached_by") else ""
        has_claude = " (resumable)" if s.get("claude_session_id") else " (fresh)"
        print(f"  {i}. {s['id'][:8]}  msgs={s['message_count']:3d}  "
              f"last={ts}  {s['status']}{has_claude}{attached}")
    print(f"  n. Create new session")
    print()

    while True:
        choice = input("Pick session [n]: ").strip().lower()
        if choice == "" or choice == "n":
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(sessions):
                return sessions[idx - 1]["id"]
        except ValueError:
            pass
        print(f"Enter 1-{len(sessions)} or 'n'")


# ---------------------------------------------------------------------------
# Claude command builder
# ---------------------------------------------------------------------------


def build_claude_cmd(
    claude_session_id: str | None,
    new_session_uuid: str | None = None,
) -> list[str]:
    """Build the claude CLI command for interactive terminal use."""
    cmd = [str(CLAUDE_BIN), "--dangerously-skip-permissions"]

    # Vault
    if VAULT.exists():
        cmd.extend(["--add-dir", str(VAULT)])

    # MCP config
    if MCP_CONFIG_PATH.exists():
        cmd.extend(["--mcp-config", str(MCP_CONFIG_PATH)])

    # Context
    if CONTEXT_CACHE.exists():
        context = CONTEXT_CACHE.read_text().strip()
        if context:
            cmd.extend(["--append-system-prompt", context])

    # Session resume or new
    if claude_session_id:
        cmd.extend(["--resume", claude_session_id])
    elif new_session_uuid:
        cmd.extend(["--session-id", new_session_uuid])

    return cmd


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    os.chdir(str(CLAWCODE_DIR))

    cfg = load_config()
    token = get_token()

    # Try gateway connection
    result = gateway_connect(cfg["host"], cfg["port"], token)

    if result is None:
        # Gateway unavailable — fall back to standalone claude
        print("Gateway unavailable — starting standalone claude session")
        cmd = build_claude_cmd(claude_session_id=None)
        os.execvp(cmd[0], cmd)
        return  # unreachable after execvp

    ws, client_id = result
    session_id = None
    claude_session_id = None
    new_session_uuid = None
    proc = None

    try:
        # List and pick session
        sessions = list_sessions(ws)
        chosen_id = pick_session(sessions)

        if chosen_id:
            # Attach to existing session
            info = attach_session(ws, chosen_id)
            if not info:
                ws.close()
                sys.exit(1)
            session_id = info["session_id"]
            claude_session_id = info.get("claude_session_id") or None
            if not claude_session_id:
                new_session_uuid = str(uuid.uuid4())
        else:
            # Create new session
            session_id = create_session(ws)
            if not session_id:
                ws.close()
                sys.exit(1)
            # Attach to the new session
            info = attach_session(ws, session_id)
            if not info:
                ws.close()
                sys.exit(1)
            new_session_uuid = str(uuid.uuid4())

        # Build claude command
        cmd = build_claude_cmd(claude_session_id, new_session_uuid)
        print(f"\nSession: {session_id[:8]}")
        if claude_session_id:
            print(f"Resuming claude session: {claude_session_id[:8]}")
        else:
            print("Starting fresh claude session")
        print()

        # Close websocket before launching claude — the open socket
        # interferes with terminal stdin. Auto-detach fires on the
        # gateway side, but we reconnect after to update claude_session_id.
        ws.close()
        ws = None

        # Run claude interactively
        proc = subprocess.run(cmd)

        # Reconnect to gateway to report claude_session_id back
        final_claude_sid = claude_session_id or new_session_uuid or ""
        if session_id and final_claude_sid:
            result2 = gateway_connect(cfg["host"], cfg["port"], token)
            if result2:
                ws2, _ = result2
                detach_session(ws2, session_id, final_claude_sid)
                ws2.close()

    except KeyboardInterrupt:
        pass
    finally:
        if ws:
            try:
                ws.close()
            except OSError:
                pass

    # Propagate claude's exit code
    if proc is not None:
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
