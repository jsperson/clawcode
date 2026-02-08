#!/bin/bash
set -e

# Daily Digest Generator for ClawCode
# Creates digest file in Obsidian vault and prints summary to stdout
# When run via schedule-runner, output goes to Discord automatically

VAULT_PATH="/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIGEST_DATE=$(date +%Y-%m-%d)
DIGEST_TIME=$(date +%H:%M)
DIGEST_DAY=$(date +%A)
DISPLAY_DATE=$(date +"%b %d, %Y")
DIGEST_FILE="$VAULT_PATH/Digests/Daily/$DIGEST_DATE.md"
TODAY_FILE="$VAULT_PATH/Digests/Today.md"

# Ensure directories exist
mkdir -p "$VAULT_PATH/Digests/Daily"

echo "=== Generating Daily Digest for $DIGEST_DATE ==="

# === COLLECT ACTIVE TASKS FROM APPLE REMINDERS ===
TASK_LIST=""
TASK_COUNT=0
OVERDUE_COUNT=0
TODAY_COUNT=0

if command -v remindctl &> /dev/null; then
  # Get overdue tasks
  overdue_json=$(remindctl overdue --json 2>/dev/null || echo "[]")
  OVERDUE_COUNT=$(echo "$overdue_json" | jq 'length' 2>/dev/null || echo "0")

  if [ "$OVERDUE_COUNT" -gt 0 ]; then
    TASK_LIST="$TASK_LIST
### Overdue"
    while IFS= read -r task; do
      [ -n "$task" ] && TASK_LIST="$TASK_LIST
$task"
      TASK_COUNT=$((TASK_COUNT + 1))
    done < <(echo "$overdue_json" | jq -r '.[] | "- **\(.listName)**: \(.title)"' 2>/dev/null)
  fi

  # Get today's tasks
  today_json=$(remindctl today --json 2>/dev/null || echo "[]")
  TODAY_COUNT=$(echo "$today_json" | jq 'length' 2>/dev/null || echo "0")

  if [ "$TODAY_COUNT" -gt 0 ]; then
    TASK_LIST="$TASK_LIST
### Due Today"
    while IFS= read -r task; do
      [ -n "$task" ] && TASK_LIST="$TASK_LIST
$task"
      TASK_COUNT=$((TASK_COUNT + 1))
    done < <(echo "$today_json" | jq -r '.[] | "- **\(.listName)**: \(.title)"' 2>/dev/null)
  fi

  # Get all incomplete tasks by list (for reference)
  TASK_LIST="$TASK_LIST
### All Active Tasks"
  for list in "Home" "Consulting" "School" "Family" "Shopping" "Side Projects"; do
    list_json=$(remindctl list "$list" --json 2>/dev/null || echo "[]")
    list_count=$(echo "$list_json" | jq '[.[] | select(.isCompleted == false)] | length' 2>/dev/null || echo "0")

    if [ "$list_count" -gt 0 ]; then
      TASK_LIST="$TASK_LIST
**$list** ($list_count):"
      while IFS= read -r task; do
        [ -n "$task" ] && TASK_LIST="$TASK_LIST
  - $task"
      done < <(echo "$list_json" | jq -r '.[] | select(.isCompleted == false) | .title' 2>/dev/null)
    fi
  done

  # Get total count
  TASK_COUNT=$(remindctl all --json 2>/dev/null | jq '[.[] | select(.isCompleted == false)] | length' 2>/dev/null || echo "0")
else
  TASK_LIST="
- remindctl not installed"
fi

# === COLLECT PROJECT CHANGES (last 24 hours) ===
PROJECT_LIST=""
PROJECT_COUNT=0
if [ -d "$VAULT_PATH/Projects" ]; then
  while IFS= read -r project_file; do
    if [ -f "$project_file" ]; then
      PROJECT_COUNT=$((PROJECT_COUNT + 1))
      rel_path="${project_file#$VAULT_PATH/Projects/}"
      project_name=$(dirname "$rel_path")
      file_name=$(basename "$project_file" .md)
      PROJECT_LIST="$PROJECT_LIST
- **$project_name**: [[$file_name]]"
    fi
  done < <(find "$VAULT_PATH/Projects" -type f -name "*.md" -mtime -1 2>/dev/null | sort)
fi

# === COLLECT CANVAS DATA ===
CANVAS_SECTION=""
CANVAS_SCRIPT="$SCRIPT_DIR/canvas-digest.py"
if [ -f "$CANVAS_SCRIPT" ]; then
  CANVAS_SECTION=$(python3 "$CANVAS_SCRIPT" 2>/dev/null || echo "Canvas digest failed")
fi

# === COLLECT CALENDAR EVENTS (today) ===
CALENDAR_LIST=""
CALENDAR_COUNT=0
if command -v icalpal &> /dev/null; then
  # icalpal reads Calendar.sqlitedb directly, requiring Full Disk Access.
  # When run from the bot (python in process chain), FDA is blocked by
  # a system TCC deny entry. Work around by spawning icalpal via a
  # launchd one-shot job so the process chain is launchd→bash→icalpal
  # with no python ancestor.
  ICAL_OUT=$(mktemp /tmp/clawcode-ical-XXXXXX.json)
  ICAL_PLIST=$(mktemp /tmp/clawcode-ical-XXXXXX.plist)
  ICAL_LABEL="com.clawcode.icalpal.$$"
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
        <string>icalpal eventsToday -o json > $ICAL_OUT 2>/dev/null</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/jsperson</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLISTEOF
  launchctl bootstrap gui/$(id -u) "$ICAL_PLIST" 2>/dev/null
  # Wait for the job to finish (icalpal runs in ~100ms)
  for i in $(seq 1 20); do
    launchctl print gui/$(id -u)/"$ICAL_LABEL" >/dev/null 2>&1 || break
    sleep 0.25
  done
  launchctl bootout gui/$(id -u)/"$ICAL_LABEL" 2>/dev/null
  rm -f "$ICAL_PLIST"

  if [ -s "$ICAL_OUT" ]; then
    calendar_json=$(cat "$ICAL_OUT")
  else
    calendar_json="[]"
  fi
  rm -f "$ICAL_OUT"

  while IFS= read -r event; do
    if [ -n "$event" ] && [ "$event" != "null" ]; then
      CALENDAR_COUNT=$((CALENDAR_COUNT + 1))
      CALENDAR_LIST="$CALENDAR_LIST
$event"
    fi
  done < <(echo "$calendar_json" | jq -r '.[] | select(.calendar != "Found in Natural Language") | "- **\(.sctime[11:16])** \(.title)"' 2>/dev/null)
else
  CALENDAR_LIST="
- icalpal not installed"
fi

# === GENERATE DIGEST FILE ===
cat > "$DIGEST_FILE" << EOF
# Daily Digest — $DIGEST_DAY, $DISPLAY_DATE
*Generated at $DIGEST_TIME*

## Top 3 Priorities
1. Review active tasks below
2. Check project updates
3. Plan the day

## Tasks ($TASK_COUNT active)
$TASK_LIST

## Today's Calendar ($CALENDAR_COUNT events)
$CALENDAR_LIST

## Project Updates ($PROJECT_COUNT files changed)
$PROJECT_LIST

$CANVAS_SECTION

## Context & Notes
Review the tasks and project updates above. Prioritize based on deadlines and importance.

---
*Generated by ClawCode Daily Digest*
EOF

echo "Digest written to: $DIGEST_FILE"

# === COPY TO TODAY.MD ===
cp "$DIGEST_FILE" "$TODAY_FILE"
echo "Today.md updated"

# === BUILD SUMMARY FOR DISCORD ===
# (schedule-runner picks up stdout and posts it)
TASK_SUMMARY="$TASK_COUNT total"
[ "$OVERDUE_COUNT" -gt 0 ] && TASK_SUMMARY="$TASK_SUMMARY, $OVERDUE_COUNT overdue"
[ "$TODAY_COUNT" -gt 0 ] && TASK_SUMMARY="$TASK_SUMMARY, $TODAY_COUNT due today"

CANVAS_DUE=$(echo "$CANVAS_SECTION" | grep -c "^- " || echo "0")
CANVAS_UNREAD=$(echo "$CANVAS_SECTION" | grep -oE "[0-9]+ unread" | head -1 || echo "")

echo ""
echo "=== Digest Summary ==="
echo "Tasks: $TASK_SUMMARY"
echo "Calendar events: $CALENDAR_COUNT"
echo "Projects changed: $PROJECT_COUNT"
echo "Canvas: $CANVAS_DUE items due soon${CANVAS_UNREAD:+, $CANVAS_UNREAD}"
echo "Daily file: $DIGEST_FILE"
echo "Obsidian: obsidian://open?vault=scott&file=Digests%2FToday"
