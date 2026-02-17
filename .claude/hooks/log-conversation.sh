#!/bin/bash
# log-conversation.sh — Append CLI conversation turns to daily log
# Called by Claude Code hooks: UserPromptSubmit and Stop
# Writes to ~/clawcode/memory/YYYY-MM-DD.md in the same format as the Discord bot
set -euo pipefail

MEMORY_DIR="$HOME/clawcode/memory"
INPUT=$(cat)
EVENT=$(echo "$INPUT" | /usr/bin/jq -r '.hook_event_name')
TODAY=$(date +"%Y-%m-%d")
NOW=$(date +"%H:%M")
LOG_FILE="$MEMORY_DIR/$TODAY.md"

# Create file with header if it doesn't exist
if [ ! -f "$LOG_FILE" ]; then
    echo "## Daily Log $TODAY" > "$LOG_FILE"
    echo "" >> "$LOG_FILE"
fi

if [ "$EVENT" = "UserPromptSubmit" ]; then
    PROMPT=$(echo "$INPUT" | /usr/bin/jq -r '.prompt // empty')
    if [ -n "$PROMPT" ]; then
        {
            echo "### $NOW"
            echo ""
            echo "**scott_person:** $PROMPT"
            echo ""
        } >> "$LOG_FILE"
    fi

elif [ "$EVENT" = "Stop" ]; then
    TRANSCRIPT=$(echo "$INPUT" | /usr/bin/jq -r '.transcript_path // empty')
    if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
        # Get the last assistant message from the transcript
        # Transcript uses .type == "assistant" (not .role) with content at .message.content[]
        RESPONSE=$(tail -50 "$TRANSCRIPT" | \
            /usr/bin/jq -s 'map(select(.type == "assistant")) | last | .message.content | map(select(.type == "text")) | map(.text) | join("\n")' -r 2>/dev/null || true)
        if [ -n "$RESPONSE" ] && [ "$RESPONSE" != "null" ] && [ -n "$RESPONSE" ]; then
            # Truncate very long responses to keep logs manageable
            TRUNCATED=$(echo "$RESPONSE" | head -50)
            LINECOUNT=$(echo "$RESPONSE" | wc -l | tr -d ' ')
            {
                echo "**Computer:** $TRUNCATED"
                if [ "$LINECOUNT" -gt 50 ]; then
                    echo ""
                    echo "*[response truncated — ${LINECOUNT} lines]*"
                fi
                echo ""
            } >> "$LOG_FILE"
        fi
    fi
fi

exit 0
