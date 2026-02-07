#!/usr/bin/env bash
# memory-sync.sh — Git add + commit memory files (called by launchd hourly)
set -euo pipefail

CLAWCODE_DIR="$HOME/clawcode"
cd "$CLAWCODE_DIR"

# Only proceed if there are changes to memory files
if git diff --quiet MEMORY.md USER.md memory/ 2>/dev/null && \
   git diff --cached --quiet MEMORY.md USER.md memory/ 2>/dev/null && \
   [ -z "$(git ls-files --others --exclude-standard MEMORY.md USER.md memory/)" ]; then
    exit 0
fi

# Stage memory files
git add MEMORY.md USER.md IDENTITY.md memory/ 2>/dev/null || true

# Commit if there are staged changes
if ! git diff --cached --quiet 2>/dev/null; then
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
    git commit -m "memory sync: $TIMESTAMP" --no-gpg-sign
fi
