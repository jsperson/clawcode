#!/usr/bin/env bash
# plugin-deploy.sh — Deploy a Claude Code plugin from marketplace to cache
#
# Usage: plugin-deploy.sh <plugin>@<marketplace>
# Example: plugin-deploy.sh life-agent@life-agent
# Example: plugin-deploy.sh compound-engineering@every-marketplace
set -euo pipefail

# --- Argument parsing ---

if [ $# -ne 1 ] || [[ "$1" != *@* ]]; then
    echo "Usage: $0 <plugin>@<marketplace>" >&2
    echo "Example: $0 life-agent@life-agent" >&2
    exit 1
fi

PLUGIN="${1%%@*}"
MARKETPLACE="${1#*@}"

if [ -z "$PLUGIN" ] || [ -z "$MARKETPLACE" ]; then
    echo "Error: Both plugin and marketplace must be non-empty" >&2
    echo "Usage: $0 <plugin>@<marketplace>" >&2
    exit 1
fi

KEY="$PLUGIN@$MARKETPLACE"

# --- Paths ---

PLUGINS_DIR="$HOME/.claude/plugins"
MARKETPLACE_DIR="$PLUGINS_DIR/marketplaces/$MARKETPLACE"
PLUGIN_SRC="$MARKETPLACE_DIR/plugins/$PLUGIN"
PLUGIN_JSON="$PLUGIN_SRC/.claude-plugin/plugin.json"
INSTALLED_JSON="$PLUGINS_DIR/installed_plugins.json"

# --- Pre-flight checks ---

if [ ! -d "$MARKETPLACE_DIR" ]; then
    echo "Error: Marketplace '$MARKETPLACE' not found at $MARKETPLACE_DIR" >&2
    exit 1
fi

# --- Git pull ---

echo "-> Pulling marketplace '$MARKETPLACE'..."
if ! git -C "$MARKETPLACE_DIR" pull --quiet; then
    echo "Error: git pull failed for marketplace '$MARKETPLACE'" >&2
    exit 1
fi

# --- Validate plugin exists ---

if [ ! -f "$PLUGIN_JSON" ]; then
    echo "Error: Plugin '$PLUGIN' not found in marketplace '$MARKETPLACE'" >&2
    echo "  Expected: $PLUGIN_JSON" >&2
    exit 1
fi

# --- Read new state ---

NEW_VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$PLUGIN_JSON")
NEW_SHA=$(git -C "$MARKETPLACE_DIR" rev-parse --short HEAD)

# --- Read old state ---

read -r OLD_VERSION OLD_SHA OLD_INSTALL_PATH < <(python3 -c "
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    entry = data['plugins']['$KEY'][0]
    print(entry.get('version', '(none)'), entry.get('gitCommitSha', '(none)')[:7], entry.get('installPath', ''))
except (KeyError, IndexError, FileNotFoundError):
    print('(none) (none) ')
" "$INSTALLED_JSON")

# --- Compare ---

if [ "$OLD_VERSION" = "$NEW_VERSION" ] && [ "$OLD_SHA" = "$NEW_SHA" ]; then
    echo "$KEY: already current ($NEW_VERSION @ $NEW_SHA)"
    exit 0
fi

# --- Deploy to cache ---

CACHE_DIR="$PLUGINS_DIR/cache/$MARKETPLACE/$PLUGIN/$NEW_VERSION"

echo "-> Deploying to cache..."
rm -rf "$CACHE_DIR"
mkdir -p "$CACHE_DIR"
cp -R "$PLUGIN_SRC/." "$CACHE_DIR/"

# --- Clean old cache ---

if [ "$OLD_VERSION" != "$NEW_VERSION" ] && [ "$OLD_VERSION" != "(none)" ]; then
    OLD_CACHE_DIR="$PLUGINS_DIR/cache/$MARKETPLACE/$PLUGIN/$OLD_VERSION"
    if [ -d "$OLD_CACHE_DIR" ]; then
        echo "-> Removing old cache ($OLD_VERSION)..."
        rm -rf "$OLD_CACHE_DIR"
    fi
fi

# --- Update installed_plugins.json ---

echo "-> Updating installed_plugins.json..."
python3 -c "
import json, sys
from datetime import datetime, timezone

path = sys.argv[1]
key = sys.argv[2]
version = sys.argv[3]
sha = sys.argv[4]
install_path = sys.argv[5]

with open(path, 'r') as f:
    data = json.load(f)

now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')

if key not in data['plugins']:
    data['plugins'][key] = [{'scope': 'user', 'installedAt': now}]

entry = data['plugins'][key][0]
entry['installPath'] = install_path
entry['version'] = version
entry['lastUpdated'] = now
entry['gitCommitSha'] = sha

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
" "$INSTALLED_JSON" "$KEY" "$NEW_VERSION" "$NEW_SHA" "$CACHE_DIR"

# --- Summary ---

echo ""
echo "=== Deployed ==="
echo "$KEY: $OLD_VERSION ($OLD_SHA) → $NEW_VERSION ($NEW_SHA)"
echo "Cache: $CACHE_DIR"
echo ""
echo "Restart Claude Code to pick up changes."
