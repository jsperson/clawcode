#!/usr/bin/env bash
# ical-query.sh — Direct passthrough to the ical CLI with default excludes
# and timezone conversion for JSON output.
#
# Historical note: this script used to spawn ical through a launchd one-shot
# to bypass TCC restrictions when invoked from a Python process chain. As of
# 2026-04-11, macOS TCC grants Calendar access directly to the Claude Code
# process chain, so the launchd detour is no longer needed — and the wrapper
# started failing with exit code 5. Simplified to a direct call.
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

# Always exclude Siri Suggestions calendar (phantom events from iMessage parsing)
DEFAULT_EXCLUDES=(--exclude-calendar "Found in Natural Language")

# Detect JSON output mode up-front so we know whether to post-process
WANT_JSON=0
for arg in "$@"; do
    case "$arg" in
        json|-o=json|--output=json) WANT_JSON=1 ;;
    esac
done
# Also catch "-o json" / "--output json" as two separate tokens
prev=""
for arg in "$@"; do
    if [ "$prev" = "-o" ] || [ "$prev" = "--output" ]; then
        [ "$arg" = "json" ] && WANT_JSON=1
    fi
    prev="$arg"
done

if [ "$WANT_JSON" -eq 1 ]; then
    # Convert UTC timestamps to local time (America/Chicago) so LLMs don't
    # have to do timezone math (DST-prone).
    "$ICAL_BIN" "${DEFAULT_EXCLUDES[@]}" "$@" | python3 -c "
import json, sys
from datetime import datetime
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
"
    exit "${PIPESTATUS[0]}"
else
    exec "$ICAL_BIN" "${DEFAULT_EXCLUDES[@]}" "$@"
fi
