#!/bin/bash
# log-conversation.sh — Append CLI conversation turns to daily log
# Called by Claude Code hooks: UserPromptSubmit and Stop
# Writes to ~/clawcode/memory/YYYY-MM-DD-cli.md in the same format as the Discord bot
set -euo pipefail

MEMORY_DIR="$HOME/clawcode/memory"
STATE_DIR="$HOME/clawcode/data"
INPUT=$(cat)
EVENT=$(echo "$INPUT" | /usr/bin/jq -r '.hook_event_name')
TODAY=$(date +"%Y-%m-%d")
NOW=$(date +"%H:%M")
LOG_FILE="$MEMORY_DIR/$TODAY-cli.md"

# Create file with structured header if it doesn't exist (matches Discord template)
if [ ! -f "$LOG_FILE" ]; then
    cat > "$LOG_FILE" <<EOF
# $TODAY

## Summary

## Key Decisions

## Tasks Completed

## Notable Information

## Open Items
EOF
fi

if [ "$EVENT" = "UserPromptSubmit" ]; then
    PROMPT=$(echo "$INPUT" | /usr/bin/jq -r '.prompt // empty')
    if [ -n "$PROMPT" ]; then
        printf '\n### %s\n\n**scott_person:** %s\n\n' "$NOW" "$PROMPT" >> "$LOG_FILE"
    fi

    # Save transcript line count so Stop hook knows where current turn starts
    TRANSCRIPT=$(echo "$INPUT" | /usr/bin/jq -r '.transcript_path // empty')
    SESSION_ID=$(echo "$INPUT" | /usr/bin/jq -r '.session_id // empty')
    if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
        LINECOUNT=$(wc -l < "$TRANSCRIPT" | tr -d ' ')
    else
        LINECOUNT=0
    fi
    if [ -n "$SESSION_ID" ]; then
        echo "$LINECOUNT" > "$STATE_DIR/.hook-offset-${SESSION_ID}"
    fi

elif [ "$EVENT" = "Stop" ]; then
    # Brief pause to let transcript flush to disk before reading
    sleep 1
    TRANSCRIPT=$(echo "$INPUT" | /usr/bin/jq -r '.transcript_path // empty')
    SESSION_ID=$(echo "$INPUT" | /usr/bin/jq -r '.session_id // empty')
    if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
        # Read offset saved by UserPromptSubmit to isolate current turn
        OFFSET_FILE="$STATE_DIR/.hook-offset-${SESSION_ID}"
        if [ -f "$OFFSET_FILE" ]; then
            OFFSET=$(cat "$OFFSET_FILE")
            # Read only lines added since the prompt was submitted
            TURN_LINES=$(tail -n +"$((OFFSET + 1))" "$TRANSCRIPT")
        else
            # No offset file — fall back to last 500 lines
            TURN_LINES=$(tail -500 "$TRANSCRIPT")
        fi

        # Extract ALL text from assistant messages in this turn (handles multi-step responses)
        RESPONSE=$(echo "$TURN_LINES" | \
            /usr/bin/jq -s '[.[] | select(.type == "assistant") | .message.content[] | select(.type == "text") | .text] | join("\n")' -r 2>/dev/null || true)
        if [ -n "$RESPONSE" ] && [ "$RESPONSE" != "null" ]; then
            # Truncate to 2000 chars (matches Discord bot truncation)
            CHARCOUNT=${#RESPONSE}
            if [ "$CHARCOUNT" -gt 2000 ]; then
                TRUNCATED="${RESPONSE:0:2000}"
                SUFFIX=$'\n\n*[response truncated — '"$CHARCOUNT"' chars]*'
            else
                TRUNCATED="$RESPONSE"
                SUFFIX=""
            fi
            printf '**Computer:** %s%s\n\n' "$TRUNCATED" "$SUFFIX" >> "$LOG_FILE"
        fi
    fi
fi

exit 0
