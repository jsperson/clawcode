---
name: notes-inbound
description: Process handwritten note images/PDFs from Obsidian vault — OCR and archive with source links
homepage: https://github.com/jsperson/clawcode
metadata:
  clawcode:
    requires:
      bins:
        - pdftoppm
  clawdbot:
    emoji: 📝
    requires:
      bins:
        - pdftoppm
        - remindctl
---

# notes-inbound

Process handwritten notes that Scott digitizes via scanning (JPG preferred, PDF supported).

## Workflow

1. **Scan** handwritten notes to JPG or PDF
2. **Drop** file in `Personal Notes/Inbound Notes/`
3. **Process** via this skill:
   - For PDFs: convert to images via `pdftoppm`
   - For JPGs: read directly (preferred — native vision, no conversion)
   - **OCR using Claude's built-in vision** to read each page/image
   - Identify date markers (`YYYYMMDD`) in left margin
   - Split content at date boundaries (multiple dates per page possible)
   - Format each date section as its own entry
4. **Insert** entries in **reverse chronological order** (newest first, right after `# Personal Notes YYYY` header)
5. **Archive** processed file to `zzArchivedPDFs/`

## Date Detection

- Scott writes dates in `YYYYMMDD` format in the **left margin**
- A single page may contain **multiple dates**
- Split content at each date marker — content below a date belongs to that date until the next date marker
- Content before the first date marker (if any) uses the filename date as fallback
- Each date section becomes a separate `## YYYYMMDD` entry in the output

## Ordering

- **Reverse chronological** — newest entries appear first in the file, right after the `# Personal Notes YYYY` header
- When inserting, find the correct position: scan existing `## YYYYMMDD` headers and insert each new entry so the file stays sorted newest-first
- A single scan with dates 20260210, 20260212, 20260213 produces three entries inserted with 20260213 closest to the top

## Output Format

Each entry in `Personal-Notes-YYYY.md`:

```markdown
## YYYYMMDD — Handwritten Notes
*Processed: HH:MM*

📎 **Source**: [[zzArchivedPDFs/filename|Original Note]]

### OCR Content

[OCR text...]

---
```

## Key Requirements

- **OCR**: Use Claude's built-in vision to read each page image directly
- **Always include source link**: `[[zzArchivedPDFs/<filename>|Original Note]]`
- **Reverse chronological** insertion — newest first
- **Date-aware splitting** — detect YYYYMMDD in left margin, split at boundaries
- Multi-page support (OCR each page)
- Archive original file after processing
- JPG files preferred over PDF (direct vision, no conversion needed)

## Invocation

User says: "process my notes" or "process written notes"

Action: Check `Personal Notes/Inbound Notes/` → OCR → Split by date → Insert reverse-chron → Archive

## Vault Paths

- **Inbound**: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Personal Notes/Inbound Notes/`
- **Archive**: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Personal Notes/zzArchivedPDFs/`
- **Output**: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Personal Notes/Personal-Notes-YYYY.md`

## Related

- Vault is added to Claude Code via `--add-dir` in the CLI wrapper
