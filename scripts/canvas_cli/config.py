"""Configuration and token loading for Canvas CLI."""

import os
import sys
from pathlib import Path

CANVAS_URL = "https://newmanu.instructure.com"
TOKEN_ENV_VAR = "CANVAS_TOKEN"
TOKEN_FILE = Path.home() / ".config" / "canvas" / "token"


def get_token():
    """Get Canvas API token from environment or config file."""
    token = os.environ.get(TOKEN_ENV_VAR)
    if token:
        return token.strip()

    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()

    print(f"Error: No Canvas token found.", file=sys.stderr)
    print(f"Set {TOKEN_ENV_VAR} environment variable or create {TOKEN_FILE}", file=sys.stderr)
    sys.exit(1)
