#!/usr/bin/env bash
# Start gmail-mcp in stdio mode with auto-refreshed access token
# Used by Claude Code as an MCP stdio server
set -euo pipefail

CLAWCODE_DIR="${CLAWCODE_DIR:-$HOME/clawcode}"
ENV_FILE="$CLAWCODE_DIR/.env"

# Read credentials from .env
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
GOOGLE_REFRESH_TOKEN=""
while IFS= read -r line; do
    case "$line" in
        GOOGLE_CLIENT_ID=*) GOOGLE_CLIENT_ID="${line#*=}" ;;
        GOOGLE_CLIENT_SECRET=*) GOOGLE_CLIENT_SECRET="${line#*=}" ;;
        GOOGLE_REFRESH_TOKEN=*) GOOGLE_REFRESH_TOKEN="${line#*=}" ;;
    esac
done < "$ENV_FILE"

if [ -z "$GOOGLE_REFRESH_TOKEN" ]; then
    echo "Error: GOOGLE_REFRESH_TOKEN not set. Run scripts/gmail-oauth-setup.sh first." >&2
    exit 1
fi

# Exchange refresh token for access token
ACCESS_TOKEN=$(curl -s -X POST https://oauth2.googleapis.com/token \
    -d "client_id=${GOOGLE_CLIENT_ID}" \
    -d "client_secret=${GOOGLE_CLIENT_SECRET}" \
    -d "refresh_token=${GOOGLE_REFRESH_TOKEN}" \
    -d "grant_type=refresh_token" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$ACCESS_TOKEN" ]; then
    echo "Error: Failed to refresh access token. Re-run scripts/gmail-oauth-setup.sh" >&2
    exit 1
fi

export GOOGLE_ACCESS_TOKEN="$ACCESS_TOKEN"
GMAIL_MCP_DIR="$(npm root -g)/gmail-mcp"
exec node "$GMAIL_MCP_DIR/dist/main.js"
