"""Load and validate ClawCode configuration from config.yaml + .env."""

from __future__ import annotations

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
class Config:
    discord: DiscordConfig
    claude: ClaudeConfig
    vault: VaultConfig
    paths: PathsConfig
    file_watch: FileWatchConfig

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

        return cls(
            discord=discord,
            claude=claude,
            vault=vault,
            paths=paths,
            file_watch=file_watch,
        )
