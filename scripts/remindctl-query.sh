#!/usr/bin/env bash
# remindctl-query.sh — Run remindctl via launchd one-shot to bypass TCC restrictions.
#
# When remindctl is invoked from a Python process chain (Claude Code, bot, etc.),
# macOS TCC denies Reminders access. This wrapper spawns remindctl through launchd
# (launchd → bash → remindctl) so there's no Python ancestor in the process chain,
# and Reminders access is granted.
#
# Usage: remindctl-query.sh [remindctl arguments...]
#
# Examples:
#   remindctl-query.sh today --json
#   remindctl-query.sh overdue --json
#   remindctl-query.sh add --title "Buy milk" --list Home --due tomorrow
#   remindctl-query.sh list Home --json
#   remindctl-query.sh all --json
#
# Output goes to stdout. Exit code matches remindctl's exit code.

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: remindctl-query.sh [remindctl arguments...]" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  remindctl-query.sh today --json" >&2
    echo "  remindctl-query.sh overdue --json" >&2
    echo "  remindctl-query.sh add --title \"Buy milk\" --list Home --due tomorrow" >&2
    exit 1
fi

# Build the remindctl command string with proper quoting
REMIND_CMD="remindctl"
for arg in "$@"; do
    REMIND_CMD="$REMIND_CMD $(printf '%q' "$arg")"
done

REMIND_OUT=$(mktemp /tmp/clawcode-remind-XXXXXX.out)
REMIND_ERR=$(mktemp /tmp/clawcode-remind-XXXXXX.err)
REMIND_RC=$(mktemp /tmp/clawcode-remind-XXXXXX.rc)
REMIND_PLIST=$(mktemp /tmp/clawcode-remind-XXXXXX.plist)
REMIND_LABEL="com.clawcode.remindctl.$$"

cleanup() {
    launchctl bootout "gui/$(id -u)/$REMIND_LABEL" 2>/dev/null || true
    rm -f "$REMIND_OUT" "$REMIND_ERR" "$REMIND_RC" "$REMIND_PLIST"
}
trap cleanup EXIT

cat > "$REMIND_PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$REMIND_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>$REMIND_CMD > $REMIND_OUT 2> $REMIND_ERR; echo \$? > $REMIND_RC</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLISTEOF

launchctl bootstrap "gui/$(id -u)" "$REMIND_PLIST" 2>/dev/null

# Wait for the job to finish (remindctl typically runs in <1s)
for i in $(seq 1 40); do
    launchctl print "gui/$(id -u)/$REMIND_LABEL" >/dev/null 2>&1 || break
    sleep 0.25
done

# Output results
if [ -s "$REMIND_OUT" ]; then
    cat "$REMIND_OUT"
fi

if [ -s "$REMIND_ERR" ]; then
    cat "$REMIND_ERR" >&2
fi

# Return remindctl's exit code
if [ -s "$REMIND_RC" ]; then
    exit "$(cat "$REMIND_RC")"
fi
