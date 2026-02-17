#!/bin/bash
# log-conversation.sh — Append CLI conversation turns to daily log
# Called by Claude Code hooks: UserPromptSubmit and Stop
# Writes to ~/clawcode/memory/YYYY-MM-DD-cli.md in the same format as the Discord bot
set -euo pipefail

MEMORY_DIR="$HOME/clawcode/memory"
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
        ENTRY=$(printf '\n### %s\n\n**scott_person:** %s\n' "$NOW" "$PROMPT")
        # Append with flock for safe concurrent writes
        (
            flock 200
            printf '%s\n' "$ENTRY" >> "$LOG_FILE"
        ) 200>"$LOG_FILE.lock"
    fi

elif [ "$EVENT" = "Stop" ]; then
    TRANSCRIPT=$(echo "$INPUT" | /usr/bin/jq -r '.transcript_path // empty')
    if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
        # Get the last assistant message from the transcript
        RESPONSE=$(tail -50 "$TRANSCRIPT" | \
            /usr/bin/jq -s 'map(select(.type == "assistant")) | last | .message.content | map(select(.type == "text")) | map(.text) | join("\n")' -r 2>/dev/null || true)
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
            # Append with flock for safe concurrent writes
            (
                flock 200
                printf '**Computer:** %s%s\n\n' "$TRUNCATED" "$SUFFIX" >> "$LOG_FILE"
            ) 200>"$LOG_FILE.lock"
        fi
    fi
fi

exit 0
