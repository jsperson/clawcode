#!/usr/bin/env bash
# install.sh — One-command ClawCode setup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="$HOME/clawcode"

echo "=== ClawCode Installer ==="
echo "Source:  $SOURCE_DIR"
echo "Install: $INSTALL_DIR"
echo ""

# ---------------------------------------------------------------------------
# 1. Copy project to ~/clawcode (if not already there)
# ---------------------------------------------------------------------------
if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    echo "→ Syncing project to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='.git' --exclude='.env' \
        --exclude='config/schedules.yaml' \
        --exclude='USER.md' --exclude='MEMORY.md' --exclude='HEARTBEAT.md' \
        "$SOURCE_DIR/" "$INSTALL_DIR/"
else
    echo "→ Already at $INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ---------------------------------------------------------------------------
# 2. Create Python virtualenv and install dependencies
# ---------------------------------------------------------------------------
echo "→ Setting up Python virtualenv..."
PYTHON="/opt/homebrew/bin/python3.13"
if [ ! -x "$PYTHON" ]; then
    echo "Error: Python 3.13 not found at $PYTHON" >&2
    echo "Install with: brew install python@3.13" >&2
    exit 1
fi
if [ ! -d .venv ]; then
    "$PYTHON" -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .

# ---------------------------------------------------------------------------
# 3. Initialize git repo
# ---------------------------------------------------------------------------
echo "→ Initializing git repo..."
if [ ! -d .git ]; then
    git init
    git add -A
    git commit -m "Initial ClawCode setup"
fi

# ---------------------------------------------------------------------------
# 4. Copy local config files from templates if missing
# ---------------------------------------------------------------------------
echo "→ Checking local config files..."

for tmpl in USER.md MEMORY.md HEARTBEAT.md; do
    if [ ! -f "$tmpl" ] && [ -f "${tmpl}.template" ]; then
        echo "  Creating $tmpl from template..."
        cp "${tmpl}.template" "$tmpl"
    fi
done

# ---------------------------------------------------------------------------
# 5. Create .env template if missing
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
    echo "→ Creating .env template..."
    cat > .env <<'ENV'
# ClawCode Discord Bot Secrets
DISCORD_TOKEN=your-discord-bot-token-here
DISCORD_CHANNEL_ID=your-channel-id-here
DISCORD_GUILD_ID=your-guild-id-here

# Gmail MCP OAuth Credentials
# Create at https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
ENV
    echo "  ⚠️  Edit .env with your Discord credentials before starting the bot."
fi

# ---------------------------------------------------------------------------
# 5b. Copy schedules.yaml from template if missing
# ---------------------------------------------------------------------------
if [ ! -f config/schedules.yaml ]; then
    echo "→ Creating config/schedules.yaml from template..."
    cp config/schedules.yaml.template config/schedules.yaml
fi

# ---------------------------------------------------------------------------
# 6. Create required directories
# ---------------------------------------------------------------------------
echo "→ Creating directories..."
mkdir -p data/logs memory/templates skills

# ---------------------------------------------------------------------------
# 7. Compile clawcal (EventKit calendar CLI)
# ---------------------------------------------------------------------------
echo "→ Compiling clawcal..."
mkdir -p bin
if swiftc -O scripts/clawcal.swift -o bin/clawcal 2>/dev/null; then
    codesign -f -s - --identifier "com.clawcode.clawcal" bin/clawcal 2>/dev/null
    echo "  Compiled bin/clawcal"
else
    echo "  ⚠️  clawcal compilation failed — calendar features will be unavailable"
fi

# ---------------------------------------------------------------------------
# 8. Symlink CLI wrapper
# ---------------------------------------------------------------------------
echo "→ Setting up CLI..."
mkdir -p "$HOME/bin"
chmod +x cli/clawcode
if [ ! -L "$HOME/bin/clawcode" ]; then
    ln -sf "$INSTALL_DIR/cli/clawcode" "$HOME/bin/clawcode"
    echo "  Symlinked ~/bin/clawcode"
fi

# Ensure ~/bin is in PATH via shell profile
if ! echo "$PATH" | grep -q "$HOME/bin"; then
    SHELL_RC="$HOME/.zshrc"
    [ -n "${BASH_VERSION:-}" ] && SHELL_RC="$HOME/.bashrc"
    if [ -f "$SHELL_RC" ] && ! grep -q '$HOME/bin' "$SHELL_RC"; then
        echo 'export PATH="$HOME/bin:$PATH"' >> "$SHELL_RC"
        echo "  Added ~/bin to PATH in $SHELL_RC"
    fi
    export PATH="$HOME/bin:$PATH"
fi

# ---------------------------------------------------------------------------
# 9. Make scripts executable
# ---------------------------------------------------------------------------
chmod +x scripts/*.sh

# ---------------------------------------------------------------------------
# 9b. Install gmail-mcp npm package (if npm available)
# ---------------------------------------------------------------------------
if command -v npm &>/dev/null; then
    if ! npm list -g gmail-mcp &>/dev/null 2>&1; then
        echo "→ Installing gmail-mcp npm package..."
        npm install -g gmail-mcp || echo "  ⚠️  gmail-mcp install failed — install manually: npm install -g gmail-mcp"
    fi
fi

# ---------------------------------------------------------------------------
# 10. Install launchd plists
# ---------------------------------------------------------------------------
echo "→ Installing launchd services..."
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS"

for plist in launchd/*.plist; do
    name=$(basename "$plist")
    label="${name%.plist}"

    cp "$plist" "$LAUNCH_AGENTS/$name"
    if launchctl print "gui/$(id -u)/$label" &>/dev/null; then
        # Already loaded — atomic kill-and-restart (no race condition)
        launchctl kickstart -k "gui/$(id -u)/$label"
    else
        # First install — bootstrap the new agent
        launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/$name" 2>/dev/null || true
    fi
    echo "  Installed $name"
done

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit ~/clawcode/.env with your Discord bot token and channel IDs"
echo "  2. Start the bot:  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.clawcode.bot.plist"
echo "  3. Or run manually: cd ~/clawcode && .venv/bin/python -m bot.main"
echo "  4. Test CLI:       clawcode 'hello'"
echo ""
echo "To start all services:"
echo "  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.clawcode.bot.plist"
echo "  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.clawcode.memory-sync.plist"
echo ""
echo "For Gmail MCP setup:"
echo "  ~/clawcode/scripts/gmail-oauth-setup.sh"
