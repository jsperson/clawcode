---
name: scott-vault
description: Scott's Obsidian vault structure, workflows, and content routing.
  Use when deciding where to file content, creating notes, or working with
  the Obsidian vault.
metadata:
  clawcode:
    emoji: "📚"
    os: ["darwin"]
---

# Scott's Obsidian Vault

**Vault path:** `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/`
iCloud-synced across devices. ~1,450 markdown files, ~2.8GB total.

## Folder Structure

```
scott/
├── Ideas/                # Early-stage captures, reference links, things to explore
├── Projects/             # Active work (folder per project, with attachments/)
│   ├── ATI/              # Consulting (Tiber Solutions)
│   ├── Newman-DataEngineering/  # Grad school coursework
│   ├── House-Yard/       # Home maintenance
│   └── ...
├── Personal Notes/       # Handwritten note digitization
│   ├── Inbound Notes/         # Drop scanned PDFs here for OCR processing
│   ├── zzArchivedPDFs/        # Processed originals (YYYYMMDD Notes.pdf)
│   ├── attachments/           # Large scanned PDFs
│   └── Personal-Notes-YYYY.md # Year-based chronological entries
├── Digests/
│   ├── Daily/            # Auto-generated daily digests (YYYY-MM-DD.md)
│   ├── Weekly/           # Weekly summaries (currently empty)
│   └── Today.md          # Current day's digest
├── Trends/               # Weekly macro trends journal (YYYY-WNN.md)
├── Clippings/            # Web clippings (currently empty)
├── working/              # Scratch/draft space for works-in-progress
├── Archive/              # Legacy OneNote import (~1,380 files), searchable, rarely modified
│   ├── 1-Important Memories/  # Family voicemails, keepsakes
│   ├── Education/        # Certs & courses (Azure, Databricks, AWS, Newman, etc.)
│   ├── Evernote/         # Paginated Evernote imports
│   ├── Geek Stuff/       # Technical references (AI, Python, Power BI, etc.)
│   ├── Knowledge/        # Training notes, professional dev, FDIC work
│   ├── Military Millions/# Business docs (J Squared LLC)
│   ├── Personal/         # Property records, vehicles, kids, scouts, media
│   ├── Tasks/            # Archived task files (legacy — tasks now in Apple Reminders)
│   └── Work/             # Client/employer folders (FDIC, Tiber, etc.)
├── _attachments/         # Legacy vault-wide attachments
└── attachments/          # Current vault-wide attachments
```

**Notes:**
- `zz` prefix = deprioritized/archived (e.g., `zzArchivedPDFs/`, `zz_SystemConfigs/`)
- Per-project `attachments/` folders are used for project-specific files

## Content Decision Tree

| Content type | Destination |
|---|---|
| Simple task/todo | Apple Reminders via `remindctl` or Siri |
| Active work with deadlines | `Projects/<ProjectName>/` (create folder) |
| Research link or idea | `Ideas/` |
| Handwritten note PDF | `Personal Notes/Inbound Notes/` |
| Web clipping | `Clippings/` |
| Draft or scratch work | `working/` |
| Completed project | Move from `Projects/` to `Archive/` |
| Everything else | Ask Scott |

## Workflows

### Notes-Inbound
**See:** `notes-inbound` skill
PDF → `Inbound Notes/` → OCR → `Personal-Notes-YYYY.md` (with `YYYYMMDD` header + PDF link) → original to `zzArchivedPDFs/`

### Daily Digest
**Schedule:** Daily at 07:00 via ClawCode
**Output:** `Digests/Daily/YYYY-MM-DD.md` + `Digests/Today.md`
**Content:** Tasks from Apple Reminders, calendar events, project updates, Canvas LMS data

### Weekly Trends
**Schedule:** Mondays at 03:00 via ClawCode
**Output:** `Trends/YYYY-WNN.md`
**Tags:** `#signal`, `#narrative-shift`, `#contrarian`, `#confirmed`, `#thread/[name]`

### Project Lifecycle
1. Create folder in `Projects/`
2. Keep notes, docs, attachments in the project folder
3. When complete, move to `Archive/` or delete

## Task System

**Tasks live in Apple Reminders**, not Obsidian.

**Lists:** Home, Consulting, School, Family, Shopping, Side Projects
**Capture:** Siri, iPhone/Watch, or `remindctl` via Computer

## Formatting Conventions

- **Dates in content:** `YYYYMMDD` headers (e.g., `20260208`)
- **File naming:** `YYYY-MM-DD.md` (digests), `YYYY-WNN.md` (trends), `Personal-Notes-YYYY.md`
- **Links:** Standard markdown links (relative paths), not wikilinks
- **Attachments:** Per-note `./attachments/` folders (Obsidian setting)
- **Notes:** Prefer atomic notes, tags optional
