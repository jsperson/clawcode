# ClawCode Disaster Recovery

How to get ClawCode running on a fresh Mac if the primary machine (Mac Studio) dies.

## What's Already Safe

| Data | Location | Sync |
|------|----------|------|
| ClawCode deploy | iCloud Drive (`clawcode_backup/`) | Nightly rsync |
| Claude Code config | iCloud Drive (`claude_config_backup/`) | Nightly rsync |
| ClawCode source | GitHub (`jsperson/clawcode`) | Manual push |
| OpenClaw source | GitHub (`jsperson/openclaw`) | Manual push |
| Life Agent plugin | GitHub (`jsperson/life-agent`) | Manual push |
| Obsidian vault | iCloud (`iCloud~md~obsidian/Documents/scott`) | Continuous |
| Secrets (.env) | Included in clawcode iCloud backup | Nightly |

## Recovery Steps

### 1. Homebrew + System Dependencies (~10 min)

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install all dependencies from Brewfile
cd ~/source/clawcode
brew bundle install
```

### 2. Node.js, Bun, npm globals (~5 min)

```bash
# Node.js (if not already present)
brew install node@22

# Bun
curl -fsSL https://bun.sh/install | bash

# npm global directory
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'

# Global packages
npm install -g openclaw gmail-mcp
```

### 3. Claude Code CLI (~2 min)

```bash
# Install Claude Code
curl -fsSL https://claude.ai/install.sh | sh

# Or if using npm:
npm install -g @anthropic-ai/claude-code
```

### 4. Deploy ClawCode (~5 min)

```bash
# Clone source (or it may already be on the machine)
git clone https://github.com/jsperson/clawcode.git ~/source/clawcode

# Deploy to ~/clawcode (copy from iCloud backup or source)
rsync -a ~/Library/Mobile\ Documents/com~apple~CloudDocs/clawcode_backup/ ~/clawcode/

# Create venv and install Python deps
cd ~/clawcode
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install launcher
mkdir -p ~/bin
cp ~/source/clawcode/cli/clawcode ~/bin/clawcode
chmod +x ~/bin/clawcode
```

### 5. Restore Claude Code Config (~2 min)

```bash
# Restore from iCloud backup
rsync -a ~/Library/Mobile\ Documents/com~apple~CloudDocs/claude_config_backup/ ~/.claude/

# Reinstall plugins (pulls fresh from GitHub)
# From within Claude Code:
#   /plugin marketplace add jsperson/life-agent
#   /plugin install life-agent@life-agent
```

### 6. OpenClaw (~10 min)

```bash
git clone https://github.com/jsperson/openclaw.git ~/openclaw

# Follow OpenClaw's own setup instructions
cd ~/openclaw
# ... (see openclaw README)
```

### 7. QMD (~15 min)

```bash
# Install QMD
bun install -g @tobilu/qmd

# Rebuild indexes (takes a few minutes — re-embeds all documents)
qmd index
qmd vector
```

### 8. Gmail OAuth (~5 min)

```bash
# Re-authorize Gmail MCP
cd ~/clawcode
bash scripts/gmail-oauth-setup.sh
```

The `.env` file (restored from iCloud backup) has the client ID and secret.
You'll need to complete the OAuth browser flow to get a fresh refresh token.

### 9. Launchd Schedules (~2 min)

```bash
# Sync schedules to launchd
clawcode schedule sync

# Verify
clawcode schedule list
```

### 10. Shell Environment

Add to `~/.zshrc`:

```bash
export PATH="$HOME/bin:$HOME/.npm-global/bin:$PATH"
export OBSIDIAN_VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
eval "$(/opt/homebrew/bin/brew shellenv)"
source "$HOME/.openclaw/completions/openclaw.zsh"
```

### 11. Verify

```bash
clawcode doctor    # Check all dependencies
clawcode           # Start interactive session
```

## What You'll Lose

Even with full recovery, some things don't survive:

- **Browser sessions** — OpenClaw's Chrome profile (cookies, logins). Re-auth everything.
- **QMD vector indexes** — Rebuilt from source docs, but takes time.
- **Launchd state** — Job history resets. Schedules themselves are recreated.
- **Any changes since last backup** — Backup runs at 01:00 nightly. Up to 24h of drift.

## Estimated Total Recovery Time

~45-60 minutes for a fully working system, assuming decent internet for brew/npm installs.

## Keeping This Current

When you add new system dependencies, MCP servers, or infrastructure:
1. Run `brew bundle dump --file=~/source/clawcode/Brewfile --force`
2. Update this doc if the recovery steps change
3. Push to GitHub
