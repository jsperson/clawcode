#!/usr/bin/env bash
# backup.sh — Rsync ~/clawcode and ~/.claude to iCloud Drive for backup (nightly)
set -euo pipefail

ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"

# --- ClawCode ---
CLAWCODE_SRC="$HOME/clawcode/"
CLAWCODE_DEST="$ICLOUD/clawcode_backup/"
mkdir -p "$CLAWCODE_DEST"

rsync -a --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv/' \
    --exclude 'data/logs/' \
    --exclude 'data/playwright-profile/' \
    --exclude '.playwright-mcp/' \
    "$CLAWCODE_SRC" "$CLAWCODE_DEST"

CLAWCODE_SIZE=$(du -sh "$CLAWCODE_DEST" | cut -f1)

# --- Claude Code config ---
CLAUDE_SRC="$HOME/.claude/"
CLAUDE_DEST="$ICLOUD/claude_config_backup/"
mkdir -p "$CLAUDE_DEST"

rsync -a --delete \
    --exclude 'debug/' \
    --exclude 'shell-snapshots/' \
    --exclude 'session-env/' \
    --exclude 'todos/' \
    --exclude 'tasks/' \
    --exclude 'plans/' \
    --exclude 'statsig/' \
    --exclude 'plugins/cache/' \
    "$CLAUDE_SRC" "$CLAUDE_DEST"

CLAUDE_SIZE=$(du -sh "$CLAUDE_DEST" | cut -f1)

echo "Backup complete: clawcode=$CLAWCODE_SIZE, claude=$CLAUDE_SIZE synced to iCloud Drive"
