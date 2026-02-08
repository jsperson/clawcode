---
name: notes-inbound
description: Process handwritten note PDFs from Obsidian vault — OCR and archive with source links
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

Process handwritten notes that Scott digitizes via PDF scanning.

## Workflow

1. **Scan** handwritten notes to PDF
2. **Drop** PDF in `Personal Notes/Inbound Notes/`
3. **Process** via this skill:
   - Convert PDF to images
   - **OCR using Qwen2.5-VL 32B** (vision model for text extraction)
   - Format entry with PDF link
4. **Archive** processed PDF to `zzArchivedPDFs/`

## Output Format

Each entry in `Personal-Notes-YYYY.md`:

```markdown
## 2026-02-04 — Handwritten Notes
*Processed: 10:28*

📎 **Source**: [[zzArchivedPDFs/filename.pdf|Original PDF]]

### OCR Content

**Page 1:**
[OCR text...]

---
```

## Key Requirements

- **OCR**: Use Claude's built-in vision to read each page image directly
- **Always include PDF link**: `[[zzArchivedPDFs/<filename>|Original PDF]]`
- Chronological insertion by processing date
- Multi-page support (OCR each page)
- Archive original PDF after processing

## Invocation

User says: "process my notes" or "process written notes"

Action: Check `Personal Notes/Inbound Notes/` → OCR → Insert with PDF link → Archive

## Vault Paths

- **Inbound**: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Personal Notes/Inbound Notes/`
- **Archive**: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Personal Notes/zzArchivedPDFs/`
- **Output**: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Personal Notes/Personal-Notes-YYYY.md`

## Related

- Vault is added to Claude Code via `--add-dir` in the CLI wrapper
