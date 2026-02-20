---
name: gmail
description: Manage Gmail — search, read, send, draft, archive, label emails.
  Use when user asks about "email", "inbox", "send email", "draft", "check mail",
  "gmail", "unread messages", "archive", or discusses email tasks.
allowed-tools: mcp__gmail-mcp__*
metadata:
  clawcode:
    emoji: "📧"
    os: ["darwin", "linux"]
    requires:
      mcp_servers: [gmail-mcp]
---

# Gmail (via gmail-mcp)

Manage Gmail through MCP tools. The `gmail-mcp` server provides 40+ tools covering messages, threads, drafts, labels, filters, and attachments.

## Safety

- **Draft first** for new emails. Create a draft, confirm with Scott, then send.
- Never auto-send emails without explicit confirmation.
- Be careful with batch operations (batch modify, batch delete).

## Quick Reference

### Search & Read

```
gmail_message_list        — Search messages (Gmail query syntax)
gmail_message_get         — Read a specific message by ID
gmail_thread_list         — List threads
gmail_thread_get          — Get full thread with all messages
```

Gmail search examples:
- `is:unread` — unread messages
- `from:someone@example.com` — from specific sender
- `subject:invoice` — by subject
- `newer_than:1d` — last 24 hours
- `has:attachment` — messages with attachments
- `in:inbox is:unread` — unread inbox messages

### Send & Reply

```
gmail_message_send        — Send a new email
gmail_draft_create        — Create a draft (preferred)
gmail_draft_send          — Send an existing draft
gmail_message_forward     — Forward a message
```

### Organize

```
gmail_message_archive     — Archive (remove from inbox)
gmail_message_trash       — Move to trash
gmail_message_modify      — Add/remove labels
gmail_message_batch_modify — Bulk label changes
gmail_label_list          — List all labels
gmail_label_create        — Create a new label
```

### Drafts

```
gmail_draft_list          — List drafts
gmail_draft_get           — Read a draft
gmail_draft_create        — Create new draft
gmail_draft_update        — Edit existing draft
gmail_draft_send          — Send a draft
gmail_draft_delete        — Delete a draft
```

### Attachments

```
gmail_attachment_get      — Download an attachment by message and attachment ID
```

**Sending attachments:** The MCP `gmail_message_send` does NOT support file attachments. To send an email with a file attached, use the script via Bash:

```bash
~/clawcode/scripts/gmail-send-attachment.sh <to> <subject> <body> <file>
```

Supports HTML, PDF, DOCX, EPUB, TXT. Uses the same OAuth credentials as gmail-mcp.

**Kindle — Send to Kindle workflow:**

Kindle's email service is picky. Use EPUB format with proper metadata:

1. Save content as HTML (with `<html lang="en">` and proper structure)
2. Convert to EPUB via calibre with language tag and no page-break splitting:
   ```bash
   ebook-convert input.html output.epub --language en --title "Title" --authors "Author" --chapter "/" --page-breaks-before "/"
   ```
3. Send:
   ```bash
   ~/clawcode/scripts/gmail-send-attachment.sh jsperson_PuR3Fa@kindle.com "Title" "See attached." output.epub
   ```

**Important Kindle gotchas:**
- **Always set `--language en`** — missing language metadata causes E999 rejection
- **Use `--chapter "/" --page-breaks-before "/"`** — prevents splitting at every `<h2>`, avoids short pages with excess whitespace
- **MOBI is dead** — Amazon no longer accepts MOBI (E001 unsupported format)
- **HTML renders poorly** on Kindle — always convert to EPUB first
- **PDF works** but has no text reflow (bad on small screens)

### Filters & Settings

```
gmail_filter_list         — List email filters
gmail_filter_create       — Create a filter
gmail_filter_delete       — Delete a filter
gmail_vacation_get        — Check vacation auto-reply status
gmail_vacation_set        — Set vacation auto-reply
```

## Tips

- Use Gmail query syntax in `gmail_message_list` — same as the Gmail search bar.
- Thread view (`gmail_thread_get`) shows the full conversation, useful for context.
- `gmail_get_profile` returns the authenticated email address and message counts.
- For batch operations, prefer `gmail_message_batch_modify` over looping single modifications.
