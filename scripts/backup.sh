#!/usr/bin/env bash
# backup.sh — Rsync ~/clawcode to iCloud Drive for backup (nightly)
set -euo pipefail

SRC="$HOME/clawcode/"
DEST="$HOME/Library/Mobile Documents/com~apple~CloudDocs/clawcode_backup/"

mkdir -p "$DEST"

rsync -a --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv/' \
    --exclude 'data/logs/' \
    --exclude 'data/playwright-profile/' \
    --exclude '.playwright-mcp/' \
    "$SRC" "$DEST"

SIZE=$(du -sh "$DEST" | cut -f1)
echo "Backup complete: $SIZE synced to iCloud Drive"
