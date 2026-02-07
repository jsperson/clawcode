# MEMORY.md - Agent Memory

## Frameworks & Mental Models

### AI Capex Judgment Framework
**Date:** 2026-02-02

**"Show me the productivity" vs "Trust the capex"** — useful framing for how markets will judge AI infrastructure spending going forward.

**Origin:** W05 2026 macro trends. Meta soared (crediting 30% engineer productivity gains from AI, $65B capex). Microsoft dropped 10% (worst since March 2020). The divergence suggests execution proof is now required — capex alone doesn't cut it.

**Application:** When tracking Big Tech AI investments, watch for concrete productivity metrics vs vague "AI infrastructure" narratives.

---

## System Configuration

### ClawCode Config
**Date:** 2026-02-07

**Project directory:** `~/clawcode/`
- Config: `config/config.yaml`
- Bot code: `bot/`
- Skills: `skills/`
- Memory: `memory/` (daily logs), `MEMORY.md`, `USER.md`, `IDENTITY.md`
- CLI wrapper: `cli/clawcode`

**Backend:** Claude Code CLI (`~/.npm-global/bin/claude`) via Max subscription
- Invoked with `--print --output-format json --session-id <uuid>`
- Sessions tracked per Discord channel, expire after 30 min inactivity

**Runs alongside OpenClaw** — separate systems, no shared state.

---

## User Identity & Accounts

### GitHub & Email
**Date:** 2026-01-24

- **GitHub username:** jsperson
- **Primary email:** jsperson@gmail.com (use for almost everything)

---

## Standard Operating Procedures

### Time & Date Format
**Date:** 2026-01-23

**Time Zone:** US Central Time (America/Chicago) with daylight saving time changes
**Time Format:** 24-hour format (e.g., 14:30, 19:22)
**Date Format:** YYYY-MM-DD (ISO 8601) when technical; human-readable when appropriate

**Examples:**
- `2026-01-23 19:22` (technical context)
- `Jan 23, 2026 at 7:22 PM` (human-readable when needed)
- Always account for DST transitions (CDT/CST)

---

## Interaction Preferences

### Decision-Making Protocol
**Date:** 2026-01-23

When Scott provides specific technical instructions (e.g., "use launchd"), do NOT shift to alternative approaches without explicit discussion first, even if encountering obstacles.

- If the requested approach hits issues: present the problem and proposed alternatives
- Wait for Scott to choose the direction
- Don't assume "getting it working" justifies deviating from explicit instructions

---

## Documentation Maintenance

### When making system changes
1. Commit and push changes to the clawcode repo
2. Update relevant documentation
3. Document new dependencies and troubleshooting steps

---

## Workflows & Commands

### Personal Notes Processing
**Date:** 2026-01-23

When Scott asks to "process my new written notes" or similar:

1. **Always check CLAUDE.md first** - Scott documents workflows in his Obsidian vault at `/scott/CLAUDE.md`
2. **Workflow documented there:**
   - Check `Personal Notes/Inbound Notes/` for new PDFs
   - Convert PDF to images (pdftoppm)
   - OCR each page using image tool
   - Insert entries chronologically into `Personal-Notes-YYYY.md`
   - Move processed PDF to `zzArchivedPDFs/`
3. **Don't ask "what should I do?"** - the workflow is documented, just execute it

---

## Skills Available

### Calendar Integration - icalpal
**Date:** 2026-01-23

The **icalpal** skill provides macOS Calendar/Reminders access via CLI.

**When to use:**
- Calendar queries (today, tomorrow, next week, etc.)
- Meeting lookups
- Event formatting for digests or notes

**Tool:** Uses `icalpal` CLI tool (installed via Homebrew)

### Apple Reminders - remindctl
**Date:** 2026-02-07

The **apple-reminders** skill manages Apple Reminders via `remindctl` CLI.

**When to use:**
- Create reminders ("remind me to...")
- List tasks (today, overdue, by list)
- Complete or delete reminders

**Tool:** Uses `remindctl` CLI tool (installed via Homebrew)
