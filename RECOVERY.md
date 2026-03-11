# ClawCode Disaster Recovery

Restore ClawCode on a fresh Mac. Written for a stock Claude Code instance to execute
step-by-step. Each step includes verification — do not proceed to the next step until
the current one passes.

## Prerequisites

- macOS on Apple Silicon (arm64)
- iCloud signed in (same Apple ID as primary machine)
- Internet access
- User: `jsperson` (paths assume this; adjust if different)

## What's Already Safe

| Data | Location | Sync |
|------|----------|------|
| ClawCode deploy | iCloud Drive `clawcode_backup/` | Nightly rsync |
| Claude Code config | iCloud Drive `claude_config_backup/` | Nightly rsync |
| ClawCode source | GitHub `jsperson/clawcode` | Manual push |
| OpenClaw source | GitHub `jsperson/openclaw` | Manual push |
| Life Agent plugin | GitHub `jsperson/life-agent` | Manual push |
| Obsidian vault | iCloud `iCloud~md~obsidian/Documents/scott` | Continuous |
| Secrets (.env) | Included in clawcode iCloud backup | Nightly |

## Step 1: Homebrew

**Depends on:** nothing

```bash
# Install Homebrew (skip if already installed)
command -v brew >/dev/null 2>&1 || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)"
```

**Verify:**
```bash
brew --version
# Expected: Homebrew 4.x+
```

## Step 2: Clone Source Repos

**Depends on:** Step 1 (need git, which macOS includes by default)

```bash
mkdir -p ~/source
git clone https://github.com/jsperson/clawcode.git ~/source/clawcode
git clone https://github.com/jsperson/openclaw.git ~/openclaw
git clone https://github.com/jsperson/life-agent.git ~/source/life-agent
```

**Verify:**
```bash
ls ~/source/clawcode/Brewfile ~/openclaw/README.md ~/source/life-agent/README.md
# All three files should exist
```

## Step 3: System Dependencies via Brewfile

**Depends on:** Steps 1, 2

```bash
cd ~/source/clawcode
brew bundle install --file=Brewfile
```

This installs: python@3.13, icalpal, remindctl, gh, pandoc, poppler, tesseract,
tmux, openclaw (cask), and all other dependencies.

**Verify:**
```bash
python3.13 --version && icalPal --version && remindctl --version && gh --version
# All should return version numbers without errors
```

## Step 4: Node.js, Bun, npm Globals

**Depends on:** Step 1

```bash
# Node.js
brew install node@22

# Bun
curl -fsSL https://bun.sh/install | bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

# npm global prefix
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
export PATH="$HOME/.npm-global/bin:$PATH"

# Global packages
npm install -g openclaw gmail-mcp
```

**Verify:**
```bash
node --version    # v22.x
bun --version     # 1.x
openclaw --version
```

## Step 5: Claude Code CLI

**Depends on:** Step 4 (needs npm/node)

```bash
npm install -g @anthropic-ai/claude-code
```

**Verify:**
```bash
claude --version
# Should return a version number
```

## Step 6: Restore ClawCode from iCloud Backup

**Depends on:** Steps 2, 3

This restores the deployed copy (config, memory, secrets, data) from the nightly backup.

```bash
# Wait for iCloud to sync if needed — check the backup directory exists
ls ~/Library/Mobile\ Documents/com~apple~CloudDocs/clawcode_backup/MEMORY.md

# Restore
rsync -a ~/Library/Mobile\ Documents/com~apple~CloudDocs/clawcode_backup/ ~/clawcode/

# Recreate the Python venv (excluded from backup)
cd ~/clawcode
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
deactivate
```

**Verify:**
```bash
ls ~/clawcode/.env ~/clawcode/MEMORY.md ~/clawcode/.mcp.json ~/clawcode/config/schedules.yaml
# All should exist

~/clawcode/.venv/bin/python --version
# Should show Python 3.13.x
```

## Step 7: Restore Claude Code Config from iCloud Backup

**Depends on:** Step 5

```bash
# Wait for iCloud to sync if needed
ls ~/Library/Mobile\ Documents/com~apple~CloudDocs/claude_config_backup/settings.json

# Restore
rsync -a ~/Library/Mobile\ Documents/com~apple~CloudDocs/claude_config_backup/ ~/.claude/
```

This restores: settings.json, life-agent config/state, plugin registrations,
conversation history, keybindings, and hooks.

**Verify:**
```bash
cat ~/.claude/settings.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('model:', d.get('model')); print('plugins:', list(d.get('enabledPlugins',{}).keys()))"
# Should show model and plugin names
```

## Step 8: Install Claude Code Plugins

**Depends on:** Step 7

Run these commands inside a Claude Code session (not bash):

```
claude
```

Then within Claude Code:
```
/plugin marketplace add jsperson/life-agent
/plugin install life-agent@life-agent
```

If the compound-engineering/every-marketplace plugin is needed, install that too per
its own instructions.

**Verify:** The plugins should appear when you run `/mcp` inside Claude Code.

## Step 9: Install Launcher

**Depends on:** Step 6

```bash
mkdir -p ~/bin
cp ~/source/clawcode/cli/clawcode ~/bin/clawcode
chmod +x ~/bin/clawcode
```

**Verify:**
```bash
~/bin/clawcode doctor
# Should run health checks (some may fail until remaining steps complete)
```

## Step 10: QMD (Search Engine)

**Depends on:** Step 4 (needs bun)

```bash
# Install QMD globally
bun install -g @tobilu/qmd

# Recreate collections that ClawCode uses
qmd collection add ~/clawcode/memory --name daily-logs --mask "**/*.md"
qmd collection add ~/clawcode --name memory --mask "MEMORY.md"
qmd collection add ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/scott --name vault-main --mask "**/*.md"

# Build indexes (this takes several minutes — embedding 1500+ docs)
qmd index
qmd vector
```

**Verify:**
```bash
qmd collection list
# Should show daily-logs, memory, vault-main with document counts > 0

qmd search "clawcode" --limit 3
# Should return results
```

## Step 11: Shell Environment

**Depends on:** All previous steps

Append to `~/.zshrc` (do NOT overwrite the file — append only):

```bash
cat >> ~/.zshrc << 'ZSHRC'

# --- ClawCode ---
export PATH="$HOME/bin:$HOME/.npm-global/bin:$PATH"
export OBSIDIAN_VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
eval "$(/opt/homebrew/bin/brew shellenv)"
source "$HOME/.openclaw/completions/openclaw.zsh" 2>/dev/null
ZSHRC
```

**Verify:**
```bash
source ~/.zshrc
which clawcode && which claude && which qmd
# All three should resolve
```

## Step 12: Launchd Schedules

**Depends on:** Steps 6, 9, 11

```bash
clawcode schedule sync
```

**Verify:**
```bash
clawcode schedule list
# Should show schedules with [active] status
```

## Step 13: Gmail OAuth (REQUIRES HUMAN)

**Depends on:** Step 6

This step requires Scott to complete a browser-based OAuth flow. Claude Code cannot
do this autonomously.

```bash
cd ~/clawcode
bash scripts/gmail-oauth-setup.sh
```

The `.env` file (restored in step 6) has the Google client ID and secret.
Scott must open the URL shown in the terminal, authorize in the browser, and paste
the code back. The script will write the refresh token to `.env`.

**Verify:**
```bash
# Start a Claude Code session and test Gmail MCP
claude -p "Use the gmail MCP tools to check how many unread emails there are"
```

## Step 14: OpenClaw Setup

**Depends on:** Steps 2, 4

OpenClaw was cloned in step 2. Additional setup:

```bash
cd ~/openclaw
openclaw setup
```

Follow any interactive prompts. This configures the gateway, browser relay, and
agent profiles.

**Note:** Browser sessions (Chrome cookies, saved logins) will NOT survive. Scott
will need to re-authenticate any sites accessed through the browser automation.

**Verify:**
```bash
openclaw status
# Should show gateway status
```

## Step 15: Final Verification

```bash
clawcode doctor
```

All checks should pass. If any fail, the doctor output includes fix instructions.

Then start an interactive session:

```bash
clawcode
```

Verify that:
- Identity loads (Computer / Starship AI banner)
- QMD search works (search for something in memory)
- MCP tools are available (`/mcp` shows servers)

## What Will Be Lost Even After Full Recovery

- **Browser sessions** — re-auth all sites in OpenClaw's Chrome profile
- **QMD vector indexes** — rebuilt in step 10 but takes time
- **Launchd job history** — resets; schedules themselves are recreated
- **Changes since last backup** — backup runs at 01:00 nightly, up to 24h of drift
- **Any uncommitted source changes** — only pushed code survives on GitHub

## Steps Requiring Human Interaction

These steps cannot be completed by Claude Code alone:

| Step | Why |
|------|-----|
| 8 | Plugin install requires interactive Claude Code session |
| 13 | Gmail OAuth requires browser-based authorization |
| 14 | OpenClaw setup may have interactive prompts |

## Estimated Recovery Time

~45-60 minutes total, assuming decent internet. QMD re-embedding (step 10) is the
longest single step at ~15 minutes.

## Keeping This Current

When infrastructure changes:
1. `brew bundle dump --file=~/source/clawcode/Brewfile --force`
2. Update this doc if recovery steps change
3. `cd ~/source/clawcode && git add -A && git commit && git push`
