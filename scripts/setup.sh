#!/usr/bin/env bash
# ClawCode First-Run Setup Wizard
# Run once on a fresh machine after cloning the repo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="$HOME/clawcode"
MCP_CONFIG="$SOURCE_DIR/config/mcp-servers.yaml"

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

step=0
total=7

next_step() {
    step=$((step + 1))
    echo ""
    echo -e "${BOLD}[$step/$total] $1${RESET}"
}

ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
fail() { echo -e "  ${RED}✗${RESET} $1"; }
info() { echo -e "  ${YELLOW}→${RESET} $1"; }

# ── Header ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}ClawCode First-Run Setup${RESET}"
echo "========================="

# ── Step 1: Homebrew dependencies ─────────────────────────────────────────────

next_step "Checking Homebrew dependencies..."

if ! command -v brew &>/dev/null; then
    fail "Homebrew not found"
    echo "  Install from https://brew.sh"
    exit 1
fi
ok "Homebrew installed"

BREW_DEPS=(python@3.13 remindctl icalpal)

for dep in "${BREW_DEPS[@]}"; do
    if brew list "$dep" &>/dev/null; then
        ok "$dep installed"
    else
        info "$dep not found — installing..."
        if brew install "$dep"; then
            ok "$dep installed"
        else
            fail "$dep install failed — install manually: brew install $dep"
        fi
    fi
done

# ── Step 2: Deploy to ~/clawcode ──────────────────────────────────────────────

next_step "Deploying to $INSTALL_DIR..."

if [ -x "$SOURCE_DIR/scripts/install.sh" ]; then
    bash "$SOURCE_DIR/scripts/install.sh"
    ok "Deployed"
else
    fail "scripts/install.sh not found"
    exit 1
fi

# ── Step 3: Discord configuration ────────────────────────────────────────────

next_step "Discord configuration"

ENV_FILE="$INSTALL_DIR/.env"
NEEDS_DISCORD=false

if [ -f "$ENV_FILE" ]; then
    # Check if values are still placeholders
    if grep -q "your-discord-bot-token-here" "$ENV_FILE"; then
        NEEDS_DISCORD=true
    else
        ok ".env already configured"
    fi
else
    NEEDS_DISCORD=true
fi

if [ "$NEEDS_DISCORD" = true ]; then
    echo ""
    echo "  Enter your Discord bot credentials."
    echo "  (Leave blank to skip — you can edit $ENV_FILE later)"
    echo ""

    read -rp "  Discord bot token: " DISCORD_TOKEN
    read -rp "  Channel ID: " CHANNEL_ID
    read -rp "  Guild ID: " GUILD_ID

    if [ -n "$DISCORD_TOKEN" ] && [ -n "$CHANNEL_ID" ] && [ -n "$GUILD_ID" ]; then
        cat > "$ENV_FILE" <<EOF
# ClawCode Discord Bot Secrets
DISCORD_TOKEN=$DISCORD_TOKEN
DISCORD_CHANNEL_ID=$CHANNEL_ID
DISCORD_GUILD_ID=$GUILD_ID
EOF
        ok ".env written"
    else
        info "Skipped — edit $ENV_FILE before starting the bot"
    fi
fi

# ── Step 4: macOS permissions ─────────────────────────────────────────────────

next_step "macOS permissions"

if command -v remindctl &>/dev/null; then
    info "Testing Reminders access..."
    if remindctl today &>/dev/null 2>&1; then
        ok "Reminders access granted"
    else
        info "Granting Reminders access..."
        info "A macOS popup should appear. Click Allow."
        remindctl authorize 2>/dev/null || true
        echo ""
        read -rp "  Press Enter after granting access in the macOS popup..."

        if remindctl today &>/dev/null 2>&1; then
            ok "Reminders access granted"
        else
            fail "Reminders access still denied"
            info "Try running 'remindctl authorize' from Terminal.app (not Tabby)"
        fi
    fi
else
    info "remindctl not installed — skipping Reminders setup"
fi

# ── Step 5: Gmail MCP setup ──────────────────────────────────────────────────

next_step "Gmail MCP (optional)"

GMAIL_READY=false

# Check if Gmail is already fully configured (has refresh token)
if [ -f "$ENV_FILE" ] && grep -q "^GOOGLE_REFRESH_TOKEN=" "$ENV_FILE"; then
    ok "Gmail OAuth already authorized"
    GMAIL_READY=true
else
    echo ""
    echo "  Gmail MCP lets Claude read, search, draft, and send emails."
    echo "  Requires a Google Cloud project with Gmail API enabled."
    echo "  Create OAuth 2.0 Web Application credentials at:"
    echo "    https://console.cloud.google.com/apis/credentials"
    echo "  Add http://localhost:9025/callback as an authorized redirect URI."
    echo ""
    echo "  (Leave blank to skip — you can run scripts/gmail-oauth-setup.sh later)"
    echo ""

    # Check if credentials already exist
    HAVE_CREDS=false
    if [ -f "$ENV_FILE" ] && grep -q "^GOOGLE_CLIENT_ID=" "$ENV_FILE" && ! grep -q "your-google-client-id" "$ENV_FILE"; then
        HAVE_CREDS=true
        ok "Google OAuth credentials already in .env"
    else
        read -rp "  Google Client ID: " GOOGLE_CLIENT_ID
        read -rp "  Google Client Secret: " GOOGLE_CLIENT_SECRET

        if [ -n "$GOOGLE_CLIENT_ID" ] && [ -n "$GOOGLE_CLIENT_SECRET" ]; then
            # Append to .env (don't overwrite existing config)
            if [ -f "$ENV_FILE" ]; then
                grep -v "^GOOGLE_CLIENT_ID=" "$ENV_FILE" | grep -v "^GOOGLE_CLIENT_SECRET=" | grep -v "^# Gmail" > "$ENV_FILE.tmp" || true
                mv "$ENV_FILE.tmp" "$ENV_FILE"
            fi
            cat >> "$ENV_FILE" <<EOF

# Gmail MCP OAuth Credentials
GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET
EOF
            ok "Gmail credentials written to .env"
            HAVE_CREDS=true
        else
            info "Skipped — run scripts/gmail-oauth-setup.sh later to configure Gmail"
        fi
    fi

    # Install gmail-mcp npm package
    if [ "$HAVE_CREDS" = true ] && command -v npm &>/dev/null; then
        if npm list -g gmail-mcp &>/dev/null 2>&1; then
            ok "gmail-mcp npm package installed"
        else
            info "Installing gmail-mcp npm package..."
            npm install -g gmail-mcp && ok "gmail-mcp installed" || fail "gmail-mcp install failed"
        fi
    fi

    # Run OAuth authorization flow
    if [ "$HAVE_CREDS" = true ]; then
        echo ""
        read -rp "  Run Google OAuth authorization now? [Y/n] " DO_OAUTH
        DO_OAUTH="${DO_OAUTH:-Y}"

        if [[ "$DO_OAUTH" =~ ^[Yy]$ ]]; then
            OAUTH_SCRIPT="$INSTALL_DIR/scripts/gmail-oauth-setup.sh"
            if [ -f "$OAUTH_SCRIPT" ]; then
                bash "$OAUTH_SCRIPT" && GMAIL_READY=true || fail "OAuth setup failed"
            else
                fail "scripts/gmail-oauth-setup.sh not found"
            fi
        else
            info "Skipped — run scripts/gmail-oauth-setup.sh later"
        fi
    fi
fi

# Register gmail-mcp as stdio MCP server
if [ "$GMAIL_READY" = true ] && command -v claude &>/dev/null; then
    claude mcp remove gmail-mcp 2>/dev/null || true
    claude mcp add gmail-mcp -- "$INSTALL_DIR/scripts/gmail-mcp-start.sh" && \
        ok "gmail-mcp registered with Claude Code" || fail "gmail-mcp registration failed"
fi

# ── Step 6: MCP server registration ──────────────────────────────────────────

next_step "MCP servers"

if [ ! -f "$MCP_CONFIG" ]; then
    info "No MCP server config found at $MCP_CONFIG"
    info "Create it when you add MCP-dependent skills"
else
    # Parse non-commented servers from YAML (simple grep-based)
    SERVERS_FOUND=false

    # Look for non-commented top-level keys under servers:
    while IFS= read -r line; do
        # Match lines like "  server-name:" (2-space indent, not commented)
        if [[ "$line" =~ ^[[:space:]]{2}[^#[:space:]][a-zA-Z0-9_-]+:$ ]]; then
            SERVERS_FOUND=true
            server_name=$(echo "$line" | sed 's/^[[:space:]]*//' | sed 's/:$//')

            info "Registering $server_name MCP server..."

            if command -v claude &>/dev/null; then
                # Check transport type (http vs stdio)
                transport=$(grep -A 20 "^  ${server_name}:" "$MCP_CONFIG" | grep "transport:" | head -1 | sed 's/.*transport:[[:space:]]*//')

                if [ "$transport" = "http" ]; then
                    # HTTP transport — parse URL
                    url=$(grep -A 20 "^  ${server_name}:" "$MCP_CONFIG" | grep "url:" | head -1 | sed 's/.*url:[[:space:]]*//')
                    if [ -n "$url" ]; then
                        claude mcp add --transport http "$server_name" "$url" && ok "$server_name registered" || fail "$server_name registration failed"
                    else
                        fail "Could not parse URL for $server_name"
                    fi
                else
                    # Stdio transport — parse command and args
                    cmd=$(grep -A 20 "^  ${server_name}:" "$MCP_CONFIG" | grep "command:" | head -1 | sed 's/.*command:[[:space:]]*//')
                    args=$(grep -A 20 "^  ${server_name}:" "$MCP_CONFIG" | grep "args:" | head -1 | sed 's/.*args:[[:space:]]*//' | tr -d '[]"')

                    if [ -n "$cmd" ]; then
                        # shellcheck disable=SC2086
                        claude mcp add "$server_name" -- $cmd $args && ok "$server_name registered" || fail "$server_name registration failed"
                    else
                        fail "Could not parse command for $server_name"
                    fi
                fi
            else
                fail "Claude CLI not found — cannot register MCP servers"
            fi
        fi
    done < "$MCP_CONFIG"

    if [ "$SERVERS_FOUND" = false ]; then
        ok "No MCP servers configured yet (template only)"
    fi
fi

# ── Step 7: Health check ─────────────────────────────────────────────────────

next_step "Health check"

info "Running clawcode doctor..."
echo ""

DOCTOR_SCRIPT="$INSTALL_DIR/scripts/doctor.py"
if [ -x "$INSTALL_DIR/.venv/bin/python" ] && [ -f "$DOCTOR_SCRIPT" ]; then
    "$INSTALL_DIR/.venv/bin/python" "$DOCTOR_SCRIPT" || true
else
    # Fall back to source dir
    if [ -f "$SOURCE_DIR/scripts/doctor.py" ]; then
        python3 "$SOURCE_DIR/scripts/doctor.py" || true
    else
        fail "doctor.py not found"
    fi
fi

# ── Offer to start ────────────────────────────────────────────────────────────

echo ""
read -rp "Start the bot now? [Y/n] " START_BOT
START_BOT="${START_BOT:-Y}"

if [[ "$START_BOT" =~ ^[Yy]$ ]]; then
    echo ""
    info "Starting ClawCode bot..."
    cd "$INSTALL_DIR"
    exec .venv/bin/python -m bot.main
else
    echo ""
    echo "To start later:"
    echo "  cd $INSTALL_DIR && .venv/bin/python -m bot.main"
    echo ""
    echo "Or via launchd:"
    echo "  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.clawcode.bot.plist"
fi
