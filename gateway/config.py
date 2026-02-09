"""Gateway-specific configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GatewayConfig:
    """Configuration for the gateway process."""

    host: str = "127.0.0.1"
    port: int = 7429
    socket_path: str = "data/gateway.sock"
    max_sessions: int = 5
    max_claude_processes: int = 3
    session_idle_timeout_minutes: int = 30
    session_expiry_minutes: int = 120
    reconnect_window_minutes: int = 5
    claude_hang_timeout_seconds: int = 120
    log_level: str = "INFO"
    auth_token: str = ""  # Loaded from GATEWAY_TOKEN env var

    @classmethod
    def from_dict(cls, raw: dict) -> GatewayConfig:
        """Build GatewayConfig from a config dict (gateway: section of config.yaml)."""
        if not raw:
            return cls()
        return cls(
            host=raw.get("host", "127.0.0.1"),
            port=int(raw.get("port", 7429)),
            socket_path=raw.get("socket_path", "data/gateway.sock"),
            max_sessions=int(raw.get("max_sessions", 5)),
            max_claude_processes=int(raw.get("max_claude_processes", 3)),
            session_idle_timeout_minutes=int(raw.get("session_idle_timeout_minutes", 30)),
            session_expiry_minutes=int(raw.get("session_expiry_minutes", 120)),
            reconnect_window_minutes=int(raw.get("reconnect_window_minutes", 5)),
            claude_hang_timeout_seconds=int(raw.get("claude_hang_timeout_seconds", 120)),
            log_level=raw.get("log_level", "INFO"),
        )
