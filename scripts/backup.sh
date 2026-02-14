#!/usr/bin/env bash
# backup.sh — Rsync ~/clawcode to Obsidian vault for iCloud backup (nightly)
set -euo pipefail

SRC="$HOME/clawcode/"
DEST="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/archive/clawcode_backup/"

mkdir -p "$DEST"

rsync -a --delete \
    --exclude '.env' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'data/logs/' \
    "$SRC" "$DEST"

SIZE=$(du -sh "$DEST" | cut -f1)
echo "Backup complete: $SIZE synced to iCloud (Obsidian vault)"
