#!/usr/bin/env python3
"""ClawCode health check — validates dependencies, permissions, and configuration."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── Colors ────────────────────────────────────────────────────────────────────

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS = f"{GREEN}PASS{RESET}"
WARN = f"{YELLOW}WARN{RESET}"
FAIL = f"{RED}FAIL{RESET}"

# ── Paths ─────────────────────────────────────────────────────────────────────

INSTALL_DIR = Path.home() / "clawcode"
SOURCE_DIR = Path(__file__).resolve().parent.parent
# Use install dir if it exists, otherwise fall back to source dir
PROJECT_DIR = INSTALL_DIR if INSTALL_DIR.exists() else SOURCE_DIR


def check(label: str, ok: bool, msg_pass: str, msg_fail: str, fix: str = "", warn: bool = False) -> bool:
    """Print a check result. Returns True if passed."""
    tag = PASS if ok else (WARN if warn else FAIL)
    detail = msg_pass if ok else msg_fail
    print(f"  [{tag}] {label}: {detail}")
    if not ok and fix:
        print(f"         Fix: {fix}")
    return ok


def section(title: str):
    print(f"\n{BOLD}{title}{RESET}")


# ── Checks ────────────────────────────────────────────────────────────────────

def check_python() -> bool:
    v = sys.version_info
    ok = v >= (3, 11)
    return check(
        "Python 3.11+",
        ok,
        f"Python {v.major}.{v.minor}.{v.micro}",
        f"Python {v.major}.{v.minor}.{v.micro} (need 3.11+)",
        fix="brew install python@3.13",
    )


def check_claude_cli() -> bool:
    return check(
        "Claude CLI",
        shutil.which("claude") is not None,
        shutil.which("claude") or "found",
        "not found",
        fix="npm install -g @anthropic-ai/claude-code",
    )


def check_discord_env() -> bool:
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        return check("Discord .env", False, "", ".env file not found",
                      fix=f"Copy .env template to {PROJECT_DIR}/.env and fill in values")

    placeholders = {"your-discord-bot-token-here", "your-channel-id-here", "your-guild-id-here"}
    content = env_file.read_text()
    has_real = True
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            val = line.split("=", 1)[1].strip()
            if val in placeholders or not val:
                has_real = False
                break

    return check(
        "Discord token",
        has_real,
        "configured",
        "placeholder values in .env",
        fix=f"Edit {PROJECT_DIR}/.env with your Discord bot token and IDs",
    )


def check_skill_bins() -> list[bool]:
    """Scan skills/*/SKILL.md for required binaries."""
    results = []
    skills_dir = PROJECT_DIR / "skills"
    if not skills_dir.exists():
        return results

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_name = skill_md.parent.name
        bins = _parse_required_bins(skill_md)
        for b in bins:
            found = shutil.which(b) is not None
            results.append(check(
                f"Skill [{skill_name}] bin: {b}",
                found,
                shutil.which(b) or "found",
                "not found",
                fix=f"brew install {b}",
            ))
    return results


def _parse_required_bins(skill_md: Path) -> list[str]:
    """Parse bins from YAML frontmatter: metadata.clawcode.requires.bins."""
    text = skill_md.read_text()
    # Simple parser — find the bins line in frontmatter
    in_frontmatter = False
    for line in text.splitlines():
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break
        if in_frontmatter and "bins:" in line:
            # Format: bins: [remindctl, icalpal]
            bracket_content = line.split("[", 1)[-1].rstrip("]").strip()
            return [b.strip() for b in bracket_content.split(",") if b.strip()]
    return []


def check_macos_reminders() -> bool:
    """Check if Reminders access works via remindctl."""
    if not shutil.which("remindctl"):
        return True  # Skip if binary not present (already flagged by skill check)

    try:
        result = subprocess.run(
            ["remindctl", "today"],
            capture_output=True, text=True, timeout=10,
        )
        # Access denied typically shows in stderr
        denied = "denied" in result.stderr.lower() or "not authorized" in result.stderr.lower()
        return check(
            "Reminders access",
            not denied and result.returncode == 0,
            "authorized",
            "access denied",
            fix="Run 'remindctl authorize' from Terminal.app, then click Allow in the macOS popup",
            warn=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return check("Reminders access", False, "", "timed out or failed",
                      fix="Run 'remindctl authorize' from Terminal.app", warn=True)


def check_venv() -> bool:
    venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
    return check(
        "Python venv",
        venv_python.exists(),
        str(venv_python),
        ".venv not found",
        fix="Run scripts/install.sh",
    )


def check_venv_packages() -> bool:
    """Verify key packages are importable from the venv."""
    venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return False  # Already flagged by check_venv

    packages = ["discord", "yaml", "dotenv", "apscheduler", "watchdog"]
    missing = []
    for pkg in packages:
        try:
            result = subprocess.run(
                [str(venv_python), "-c", f"import {pkg}"],
                capture_output=True, timeout=10,
            )
            if result.returncode != 0:
                missing.append(pkg)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            missing.append(pkg)

    return check(
        "Venv packages",
        len(missing) == 0,
        "all present",
        f"missing: {', '.join(missing)}",
        fix=f"cd {PROJECT_DIR} && .venv/bin/pip install -e .",
    )


def check_config_paths() -> list[bool]:
    """Validate paths in config/config.yaml exist."""
    results = []
    config_file = PROJECT_DIR / "config" / "config.yaml"
    if not config_file.exists():
        results.append(check("Config file", False, "", "config/config.yaml not found",
                             fix="Run scripts/install.sh"))
        return results

    # Simple path extraction without requiring yaml in this script's environment
    text = config_file.read_text()
    paths_to_check = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("path:") and "~/" in line:
            val = line.split(":", 1)[1].strip()
            expanded = os.path.expanduser(val)
            paths_to_check[val] = expanded
        if line.startswith("project_dir:") or line.startswith("skills_dir:") or \
           line.startswith("memory_dir:") or line.startswith("data_dir:"):
            val = line.split(":", 1)[1].strip()
            if "~/" in val:
                expanded = os.path.expanduser(val)
                paths_to_check[val] = expanded

    for label, expanded in paths_to_check.items():
        results.append(check(
            f"Path: {label}",
            os.path.exists(expanded),
            "exists",
            "not found",
            fix=f"Check config/config.yaml — expected path: {expanded}",
            warn=True,
        ))
    return results


def check_mcp_servers() -> bool:
    """Check if expected MCP servers from config/mcp-servers.yaml are registered."""
    mcp_config = PROJECT_DIR / "config" / "mcp-servers.yaml"
    if not mcp_config.exists():
        return check("MCP config", False, "", "config/mcp-servers.yaml not found",
                      fix="Create config/mcp-servers.yaml", warn=True)

    # Parse expected servers (non-commented)
    expected = _parse_mcp_servers(mcp_config)
    if not expected:
        return check("MCP servers", True, "no servers configured (template only)", "", warn=False)

    # Check .claude/mcp.json for registered servers
    mcp_json = PROJECT_DIR / ".claude" / "mcp.json"
    if not mcp_json.exists():
        return check(
            "MCP servers",
            False,
            "",
            f"{len(expected)} server(s) expected but .claude/mcp.json not found",
            fix="Run scripts/setup.sh to register MCP servers",
        )

    import json
    try:
        registered = json.loads(mcp_json.read_text())
        registered_names = set(registered.get("mcpServers", {}).keys())
    except (json.JSONDecodeError, KeyError):
        registered_names = set()

    missing = [s for s in expected if s not in registered_names]
    if missing:
        return check(
            "MCP servers",
            False,
            "",
            f"missing: {', '.join(missing)}",
            fix="Run scripts/setup.sh to register MCP servers",
        )
    return check("MCP servers", True, f"{len(expected)} registered", "")


def check_gmail_mcp() -> list[bool]:
    """Gmail-MCP specific checks: credentials, process, registration."""
    results = []
    mcp_config = PROJECT_DIR / "config" / "mcp-servers.yaml"

    # Only run if gmail-mcp is configured
    if not mcp_config.exists():
        return results
    expected = _parse_mcp_servers(mcp_config)
    if "gmail-mcp" not in expected:
        return results

    # Check OAuth credentials in .env
    env_file = PROJECT_DIR / ".env"
    has_client_id = False
    has_client_secret = False
    if env_file.exists():
        content = env_file.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key == "GOOGLE_CLIENT_ID" and val and not val.startswith("your-"):
                has_client_id = True
            if key == "GOOGLE_CLIENT_SECRET" and val and not val.startswith("your-"):
                has_client_secret = True

    results.append(check(
        "Gmail OAuth credentials",
        has_client_id and has_client_secret,
        "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET set",
        "missing or placeholder values in .env",
        fix=f"Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to {PROJECT_DIR}/.env",
    ))

    # Check refresh token
    has_refresh = False
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key.strip() == "GOOGLE_REFRESH_TOKEN" and val.strip():
                has_refresh = True

    results.append(check(
        "Gmail refresh token",
        has_refresh,
        "GOOGLE_REFRESH_TOKEN set",
        "missing — OAuth not completed",
        fix="Run: ~/clawcode/scripts/gmail-oauth-setup.sh",
    ))

    return results


def _parse_mcp_servers(mcp_config: Path) -> list[str]:
    """Parse non-commented server names from mcp-servers.yaml."""
    servers = []
    text = mcp_config.read_text()
    in_servers = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "servers:":
            in_servers = True
            continue
        if in_servers and not stripped.startswith("#") and stripped.endswith(":"):
            # Top-level key under servers: (not indented sub-keys)
            indent = len(line) - len(line.lstrip())
            if indent == 2:  # Direct child of servers:
                servers.append(stripped.rstrip(":"))
    return servers


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}ClawCode Doctor{RESET}")
    print(f"Project: {PROJECT_DIR}\n")

    all_ok = True

    section("Core Dependencies")
    all_ok &= check_python()
    all_ok &= check_claude_cli()
    all_ok &= check_discord_env()

    section("Skill Dependencies")
    for result in check_skill_bins():
        all_ok &= result

    section("macOS Permissions")
    all_ok &= check_macos_reminders()

    section("Environment")
    all_ok &= check_venv()
    all_ok &= check_venv_packages()

    section("Configuration")
    for result in check_config_paths():
        all_ok &= result
    all_ok &= check_mcp_servers()

    section("MCP Services")
    for result in check_gmail_mcp():
        all_ok &= result

    print()
    if all_ok:
        print(f"{GREEN}{BOLD}All checks passed.{RESET}")
    else:
        print(f"{YELLOW}{BOLD}Some checks need attention. See fix suggestions above.{RESET}")
    print()

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
