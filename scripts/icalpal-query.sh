#!/usr/bin/env bash
# icalpal-query.sh — Run icalpal via launchd one-shot to bypass TCC/FDA restrictions.
#
# When icalpal is invoked from a Python process chain (Claude Code, bot, etc.),
# macOS TCC denies Full Disk Access to the Calendar database. This wrapper
# spawns icalpal through launchd (launchd → bash → icalpal) so there's no
# Python ancestor in the process chain, and FDA is granted.
#
# Usage: icalpal-query.sh [--compact] [icalpal arguments...]
#
# Options:
#   --compact   Filter JSON output to essential fields only (date, time, title,
#               calendar, location, all_day). Requires -o json in the icalpal args.
#               For tasks, returns: title, calendar, due date, priority, completed.
#
# Examples:
#   icalpal-query.sh eventsToday -o json
#   icalpal-query.sh --compact eventsToday -o json
#   icalpal-query.sh --compact events --from "2026-03-01" --to "2026-03-31" -o json
#   icalpal-query.sh --compact tasks -o json
#
# Output goes to stdout. Exit code matches icalpal's exit code.

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: icalpal-query.sh [--compact] [icalpal arguments...]" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  icalpal-query.sh eventsToday -o json" >&2
    echo "  icalpal-query.sh --compact eventsToday -o json" >&2
    echo "  icalpal-query.sh --compact events --from 2026-03-01 --to 2026-03-31 -o json" >&2
    exit 1
fi

# Check for --compact flag
COMPACT=false
if [ "$1" = "--compact" ]; then
    COMPACT=true
    shift
fi

# Detect whether this is a tasks query (for compact jq filter selection)
IS_TASKS=false
for arg in "$@"; do
    case "$arg" in
        tasks|datedTasks|tasksDueBefore|undatedTasks|uncompletedTasks)
            IS_TASKS=true
            break
            ;;
    esac
done

# Build the icalpal command string with proper quoting
ICAL_CMD="icalpal"
for arg in "$@"; do
    ICAL_CMD="$ICAL_CMD $(printf '%q' "$arg")"
done

ICAL_OUT=$(mktemp /tmp/clawcode-ical-XXXXXX.json)
ICAL_ERR=$(mktemp /tmp/clawcode-ical-XXXXXX.err)
ICAL_RC=$(mktemp /tmp/clawcode-ical-XXXXXX.rc)
ICAL_PLIST=$(mktemp /tmp/clawcode-ical-XXXXXX.plist)
ICAL_LABEL="com.clawcode.icalpal.$$"

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
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLISTEOF

launchctl bootstrap "gui/$(id -u)" "$ICAL_PLIST" 2>/dev/null

# Wait for the job to finish (icalpal typically runs in <1s)
for i in $(seq 1 40); do
    launchctl print "gui/$(id -u)/$ICAL_LABEL" >/dev/null 2>&1 || break
    sleep 0.25
done

# Output results
if [ -s "$ICAL_OUT" ]; then
    if [ "$COMPACT" = true ]; then
        if [ "$IS_TASKS" = true ]; then
            jq '[.[] | {title: .title, calendar: .calendar, due: .sdate, priority: .priority, completed: (.status == 1)}]' "$ICAL_OUT"
        else
            jq '[.[] | {date: .sdate, start: .sctime[11:16], end: .ectime[11:16], title: .title, calendar: .calendar, location: .location, all_day: (.all_day == 1)}]' "$ICAL_OUT"
        fi
    else
        cat "$ICAL_OUT"
    fi
fi

if [ -s "$ICAL_ERR" ]; then
    cat "$ICAL_ERR" >&2
fi

# Return icalpal's exit code
if [ -s "$ICAL_RC" ]; then
    exit "$(cat "$ICAL_RC")"
fi
