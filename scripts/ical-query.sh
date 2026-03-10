#!/usr/bin/env bash
# ical-query.sh — Run ical CLI via launchd one-shot to bypass TCC restrictions.
#
# When ical is invoked from a Python process chain (Claude Code, bot, etc.),
# macOS TCC denies Calendar access via EventKit. This wrapper spawns ical
# through launchd (launchd → bash → ical) so there's no Python ancestor
# in the process chain, and Calendar access is granted.
#
# Usage: ical-query.sh [ical arguments...]
#
# Examples:
#   ical-query.sh today -o json
#   ical-query.sh upcoming --days 7 -o json
#   ical-query.sh list --from today --to "next friday" -o json
#   ical-query.sh add "Dentist" --start "mar 15 at 2pm" --end "mar 15 at 3pm"
#   ical-query.sh calendars -o json
#
# Output goes to stdout. Exit code matches ical's exit code.

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: ical-query.sh [ical arguments...]" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  ical-query.sh today -o json" >&2
    echo "  ical-query.sh upcoming --days 7 -o json" >&2
    echo "  ical-query.sh add \"Meeting\" --start \"tomorrow at 9am\"" >&2
    exit 1
fi

ICAL_BIN="$(command -v ical 2>/dev/null || echo "$HOME/.local/bin/ical")"

# Build the ical command string with proper quoting
ICAL_CMD="$ICAL_BIN"
for arg in "$@"; do
    ICAL_CMD="$ICAL_CMD $(printf '%q' "$arg")"
done

ICAL_OUT=$(mktemp /tmp/clawcode-ical-XXXXXX.out)
ICAL_ERR=$(mktemp /tmp/clawcode-ical-XXXXXX.err)
ICAL_RC=$(mktemp /tmp/clawcode-ical-XXXXXX.rc)
ICAL_PLIST=$(mktemp /tmp/clawcode-ical-XXXXXX.plist)
ICAL_LABEL="com.clawcode.ical.$$"

cleanup() {
    launchctl bootout "gui/$(id -u)/$ICAL_LABEL" 2>/dev/null || true
    rm -f "$ICAL_OUT" "$ICAL_ERR" "$ICAL_RC" "$ICAL_PLIST"
}
trap cleanup EXIT

cat > "$ICAL_PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$ICAL_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>$ICAL_CMD > $ICAL_OUT 2> $ICAL_ERR; echo \$? > $ICAL_RC</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLISTEOF

launchctl bootstrap "gui/$(id -u)" "$ICAL_PLIST" 2>/dev/null

# Wait for the job to finish (ical typically runs in <1s)
for i in $(seq 1 40); do
    launchctl print "gui/$(id -u)/$ICAL_LABEL" >/dev/null 2>&1 || break
    sleep 0.25
done

# Output results
if [ -s "$ICAL_OUT" ]; then
    # If JSON output, convert UTC timestamps to local time (America/Chicago)
    # so LLMs don't have to do timezone math (DST-prone)
    if echo "$ICAL_CMD" | grep -q -- '-o json\|--output json'; then
        python3 -c "
import json, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

tz = ZoneInfo('America/Chicago')
data = json.load(sys.stdin)
items = data if isinstance(data, list) else [data]
for item in items:
    for key in ('start_date', 'end_date'):
        val = item.get(key, '')
        if val and val.endswith('Z'):
            dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
            item[key] = dt.astimezone(tz).isoformat()
json.dump(data, sys.stdout, indent=2)
print()
" < "$ICAL_OUT" 2>/dev/null || cat "$ICAL_OUT"
    else
        cat "$ICAL_OUT"
    fi
fi

if [ -s "$ICAL_ERR" ]; then
    cat "$ICAL_ERR" >&2
fi

# Return ical's exit code
if [ -s "$ICAL_RC" ]; then
    exit "$(cat "$ICAL_RC")"
fi
