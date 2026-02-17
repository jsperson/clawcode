#!/usr/bin/env bash
# memory-sync.sh — Git add + commit curated memory files (called by launchd hourly)
# NOTE: Daily logs (memory/*.md) are NOT committed — they stay on disk only,
# indexed by QMD for search. Only curated files go into git.
set -euo pipefail

CLAWCODE_DIR="$HOME/clawcode"
cd "$CLAWCODE_DIR"

# Only check curated files (not daily logs in memory/)
if git diff --quiet MEMORY.md USER.md IDENTITY.md 2>/dev/null && \
   git diff --cached --quiet MEMORY.md USER.MD IDENTITY.md 2>/dev/null; then
    exit 0
fi

# Stage curated files only
git add MEMORY.md USER.md IDENTITY.md 2>/dev/null || true

# Commit if there are staged changes
if ! git diff --cached --quiet 2>/dev/null; then
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
    git commit -m "memory sync: $TIMESTAMP" --no-gpg-sign
fi
