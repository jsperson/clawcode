"""Load and validate ClawCode configuration from config.yaml + .env."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


def _expand(value: str) -> str:
    """Expand ~ and ${ENV_VAR} references in a string value."""
    # Substitute ${VAR} with environment variable
    value = re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1), m.group(0)),
        value,
    )
    return str(Path(value).expanduser())


@dataclass
class DiscordConfig:
    channel_id: int
    guild_id: int


@dataclass
class ClaudeConfig:
    path: str
    timeout_seconds: int = 300
    session_expiry_minutes: int = 30


@dataclass
class VaultConfig:
    path: str


@dataclass
class PathsConfig:
    project_dir: str
    skills_dir: str
    memory_dir: str
    data_dir: str


@dataclass
class WatchEntry:
    path: str
    on: str
    action: str
    prompt: str


@dataclass
class FileWatchConfig:
    enabled: bool = True
    debounce_seconds: int = 5
    ignore_patterns: list[str] = field(default_factory=list)
    watches: list[WatchEntry] = field(default_factory=list)


@dataclass
class MCPServerConfig:
    name: str
    transport: str  # "stdio" or "http"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPConfig:
    servers: list[MCPServerConfig] = field(default_factory=list)


@dataclass
class GatewayConfig:
    """Gateway process configuration (optional — only needed when gateway is running)."""

    host: str = "127.0.0.1"
    port: int = 7429
    socket_path: str = "data/gateway.sock"
    max_sessions: int = 5
    max_claude_processes: int = 3
    session_idle_timeout_minutes: int = 30
    session_expiry_minutes: int = 120
    reconnect_window_minutes: int = 5
    claude_hang_timeout_seconds: int = 120
    auth_token: str = ""
    enabled: bool = False  # Feature flag: bot routes through gateway when True


@dataclass
class Config:
    discord: DiscordConfig
    claude: ClaudeConfig
    vault: VaultConfig
    paths: PathsConfig
    file_watch: FileWatchConfig
    mcp: MCPConfig = field(default_factory=MCPConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        """Load configuration from YAML file and environment variables."""
        project_dir = Path(__file__).resolve().parent.parent
        if config_path is None:
            config_path = project_dir / "config" / "config.yaml"
        else:
            config_path = Path(config_path)

        # Load .env from project root
        env_path = project_dir / ".env"
        load_dotenv(env_path)

        with open(config_path) as f:
            raw = yaml.safe_load(f)

        discord = DiscordConfig(
            channel_id=int(_expand(str(raw["discord"]["channel_id"]))),
            guild_id=int(_expand(str(raw["discord"]["guild_id"]))),
        )

        claude_raw = raw["claude"]
        claude = ClaudeConfig(
            path=_expand(claude_raw["path"]),
            timeout_seconds=claude_raw.get("timeout_seconds", 300),
            session_expiry_minutes=claude_raw.get("session_expiry_minutes", 30),
        )

        vault = VaultConfig(path=_expand(raw["vault"]["path"]))

        paths_raw = raw["paths"]
        paths = PathsConfig(
            project_dir=_expand(paths_raw["project_dir"]),
            skills_dir=_expand(paths_raw["skills_dir"]),
            memory_dir=_expand(paths_raw["memory_dir"]),
            data_dir=_expand(paths_raw["data_dir"]),
        )

        fw_raw = raw.get("file_watch", {})
        watches = []
        for w in fw_raw.get("watches", []):
            watch_path = w["path"]
            # Replace ${vault_path} with actual vault path
            watch_path = watch_path.replace("${vault_path}", vault.path)
            watches.append(WatchEntry(
                path=watch_path,
                on=w["on"],
                action=w["action"],
                prompt=w["prompt"],
            ))

        file_watch = FileWatchConfig(
            enabled=fw_raw.get("enabled", True),
            debounce_seconds=fw_raw.get("debounce_seconds", 5),
            ignore_patterns=fw_raw.get("ignore_patterns", []),
            watches=watches,
        )

        # MCP server configuration (optional)
        mcp = MCPConfig()
        mcp_path = project_dir / "config" / "mcp-servers.yaml"
        if mcp_path.exists():
            try:
                with open(mcp_path) as f:
                    mcp_raw = yaml.safe_load(f) or {}
                for name, srv in (mcp_raw.get("servers") or {}).items():
                    transport = srv.get("transport", "stdio")
                    command = srv.get("command")
                    if command:
                        command = _expand(command)
                    args = [_expand(str(a)) for a in (srv.get("args") or [])]
                    url = srv.get("url")
                    if url:
                        url = _expand(url)
                    env = {
                        k: _expand(str(v))
                        for k, v in (srv.get("env") or {}).items()
                    }
                    mcp.servers.append(MCPServerConfig(
                        name=name,
                        transport=transport,
                        command=command,
                        args=args,
                        url=url,
                        env=env,
                    ))
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "Failed to parse mcp-servers.yaml: %s", e
                )

        # Gateway configuration (optional)
        gw_raw = raw.get("gateway", {}) or {}
        gateway = GatewayConfig(
            host=gw_raw.get("host", "127.0.0.1"),
            port=int(gw_raw.get("port", 7429)),
            socket_path=gw_raw.get("socket_path", "data/gateway.sock"),
            max_sessions=int(gw_raw.get("max_sessions", 5)),
            max_claude_processes=int(gw_raw.get("max_claude_processes", 3)),
            session_idle_timeout_minutes=int(gw_raw.get("session_idle_timeout_minutes", 30)),
            session_expiry_minutes=int(gw_raw.get("session_expiry_minutes", 120)),
            reconnect_window_minutes=int(gw_raw.get("reconnect_window_minutes", 5)),
            claude_hang_timeout_seconds=int(gw_raw.get("claude_hang_timeout_seconds", 120)),
            auth_token=os.environ.get("GATEWAY_TOKEN", ""),
            enabled=gw_raw.get("enabled", False),
        )

        return cls(
            discord=discord,
            claude=claude,
            vault=vault,
            paths=paths,
            file_watch=file_watch,
            mcp=mcp,
            gateway=gateway,
        )
