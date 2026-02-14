#!/bin/bash
# heartbeat-health.sh — Check if the ClawCode bot is alive, restart if dead.
# Run via launchd every 6 hours as a safety net.

set -euo pipefail

SERVICE="com.clawcode.bot"
GUI_TARGET="gui/$(id -u)"
SERVICE_TARGET="${GUI_TARGET}/${SERVICE}"
LOG_DIR="$HOME/clawcode/data/logs"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [healthcheck] $*"
}

# Check if the bot service has a running PID
check_alive() {
    local pid
    pid=$(launchctl list "$SERVICE" 2>/dev/null | awk '/PID/ { print $NF }')
    if [[ -n "$pid" && "$pid" != "-" && "$pid" != "0" ]]; then
        return 0
    fi
    return 1
}

log "Health check starting"

if check_alive; then
    log "Bot is alive"
    exit 0
fi

log "Bot is NOT running — attempting restart"
launchctl kickstart -k "$SERVICE_TARGET" 2>/dev/null || true

# Wait for startup
sleep 15

if check_alive; then
    log "Bot restarted successfully"
    exit 0
fi

# Still dead — send macOS notification
log "Bot failed to restart — sending notification"
osascript -e 'display notification "ClawCode bot failed to restart. Check logs." with title "ClawCode Health Check" sound name "Basso"' 2>/dev/null || true

exit 1
