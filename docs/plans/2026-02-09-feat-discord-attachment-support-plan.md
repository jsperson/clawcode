---
title: Discord Attachment Support
type: feat
date: 2026-02-09
---

# Discord Attachment Support

## Overview

Pass Discord file attachments (images, text files) through the gateway to Claude CLI via stream-json content blocks. Currently, when a Discord user attaches a file to a message, the bot extracts only the text and silently drops the attachment. Image-only messages (no text) are silently dropped entirely.

## Problem Statement

The bot's `on_message` handler (`bot/main.py:229`) extracts `message.content` (text only) and ignores `message.attachments`. Line 230 returns early if there's no text, meaning a message with only an image is completely invisible to Claude. The stream-json input format already supports image content blocks — the pipeline just isn't wiring them through.

## Proposed Solution

Thread attachments through the existing pipeline with an additive `attachments` field. Each layer gets a small change — no type signature breaks, full backwards compatibility for text-only messages.

```
Discord message with image
  -> Bot downloads attachment, base64 encodes, detects media type
  -> WebSocket: {"type":"message", "content":"text", "attachments":[...]}
  -> Router builds content blocks: [text_block, image_block, ...]
  -> ClaudeProcess.send_message sends content blocks via stream-json
  -> Claude processes the image, streams response back
```

### What's Supported

| Type | Handling |
|------|----------|
| Images (jpeg, png, gif, webp) | Base64-encoded image content block |
| Text files (.py, .txt, .json, .csv, .md, etc.) | Decoded UTF-8, injected as text block with filename header |
| Everything else (PDFs, zips, binary) | Silently skipped |

### Limits

- 10 MB per attachment (Discord allows up to 25 MB, but leaves headroom for base64 + JSON overhead)
- 5 attachments per message
- 20 MB total WebSocket frame size

## Technical Approach

### 1. Protocol — `gateway/protocol.py`

Add optional `attachments` field to `UserMessage`:

```python
@dataclass
class UserMessage:
    type: str = field(default="message", init=False)
    session_id: str = ""
    content: str = ""
    attachments: list[dict[str, Any]] = field(default_factory=list)
```

Each attachment dict: `{"filename": str, "content_type": str, "data": str}` where `data` is base64-encoded. `parse_request` already picks up new dataclass fields via the kwargs loop — no changes needed there. Text-only messages send `attachments: []` or omit the field entirely.

### 2. Claude Pool — `gateway/claude_pool.py`

Add optional `attachments` param to `send_message`. Build content blocks array:

```python
async def send_message(self, content: str, attachments: list[dict] | None = None) -> None:
    blocks = []
    if content:
        blocks.append({"type": "text", "text": content})

    for att in (attachments or []):
        ct = att["content_type"]
        if ct.startswith("image/"):
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": ct, "data": att["data"]},
            })
        else:
            # Text file — decode and inject as labeled text block
            try:
                text = base64.b64decode(att["data"]).decode("utf-8", errors="replace")
                blocks.append({"type": "text", "text": f"[{att['filename']}]\n{text}"})
            except Exception:
                pass

    # Image-only: if no text was provided and only image blocks, that's fine —
    # Claude handles image-only inputs
    if not blocks:
        return  # nothing to send

    msg = json.dumps({
        "type": "user",
        "message": {"role": "user", "content": blocks},
    })
    self.proc.stdin.write((msg + "\n").encode("utf-8"))
    await self.proc.stdin.drain()
```

Add `import base64` to the file.

### 3. Router — `gateway/router.py`

Pass attachments from the protocol message through to claude. Store metadata placeholder in history, not base64 blobs:

```python
# _handle_message: pass req.attachments through
await self._route_to_claude(client, session_id, session, req.content, req.attachments)

# _route_to_claude signature adds attachments param
async def _route_to_claude(self, client, session_id, session, content, attachments=None):
    # Record user message — text + attachment metadata, no blobs
    history_content = content
    for att in (attachments or []):
        size_kb = len(att.get("data", "")) * 3 // 4 // 1024
        history_content += f"\n[attachment: {att['filename']}, {size_kb}KB]"
    self._sessions.add_message(session_id, "user", history_content, source)

    # ... existing process spawn logic ...

    await cp.send_message(content, attachments=attachments)
```

### 4. Gateway Client — `bot/gateway_client.py`

Add optional `attachments` parameter to `send_message`:

```python
async def send_message(self, channel_id: str, content: str,
                       attachments: list[dict] | None = None) -> str:
    # ... existing session logic ...
    msg = json.dumps({
        "type": "message",
        "session_id": session_id,
        "content": content,
        "attachments": attachments or [],
    })
```

### 5. Discord Bot — `bot/main.py`

Extract and download attachments in `on_message`. Allow image-only messages:

```python
user_text = message.content.strip()
attachments = await _download_attachments(message.attachments)

# Allow image-only messages
if not user_text and not attachments:
    return
```

New module-level helper:

```python
import base64
from pathlib import Path

IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
TEXT_EXTENSIONS = {".py", ".txt", ".json", ".csv", ".md", ".yaml", ".yml",
                   ".js", ".ts", ".html", ".css", ".sh", ".rb", ".rs",
                   ".go", ".swift", ".sql", ".xml", ".toml", ".ini", ".log"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ATTACHMENTS = 5


def _detect_image_type(data: bytes) -> str | None:
    """Detect image type from magic bytes. Returns MIME type or None."""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if data[:2] == b'\xff\xd8':
        return "image/jpeg"
    if data[:4] == b'GIF8':
        return "image/gif"
    if data[:4] == b'RIFF' and len(data) > 12 and data[8:12] == b'WEBP':
        return "image/webp"
    return None


async def _download_attachments(discord_attachments) -> list[dict]:
    """Download and encode Discord attachments for the gateway."""
    results = []
    for att in discord_attachments[:MAX_ATTACHMENTS]:
        if att.size > MAX_FILE_SIZE:
            logger.warning("Skipping oversized attachment: %s (%d bytes)", att.filename, att.size)
            continue

        content_type = att.content_type or ""
        ext = Path(att.filename).suffix.lower()
        is_image = content_type.startswith("image/")
        is_text = ext in TEXT_EXTENSIONS

        if not is_image and not is_text:
            continue

        try:
            data = await att.read()
        except Exception:
            logger.warning("Failed to download attachment: %s", att.filename)
            continue

        if is_image:
            detected = _detect_image_type(data)
            if not detected:
                continue  # not a valid image
            content_type = detected  # trust magic bytes over extension

        results.append({
            "filename": att.filename,
            "content_type": content_type if is_image else "text/plain",
            "data": base64.b64encode(data).decode("ascii"),
        })
        logger.info("Attachment: %s (%d bytes, %s)", att.filename, len(data), content_type)

    return results
```

### 6. WebSocket Frame Size — `gateway/server.py` + `bot/gateway_client.py`

Increase max frame size to accommodate base64 payloads:

```python
# Server: websockets.serve(..., max_size=20_000_000)
# Client: websockets.connect(..., max_size=20_000_000)
```

### 7. Legacy Fallback — `bot/main.py`

The `ClaudeBridge.invoke` direct path doesn't support attachments. Log and skip:

```python
if attachments:
    logger.info("Attachments dropped — gateway unavailable")
response = await bridge.invoke(message=user_text, ...)
```

## Edge Cases

| Case | Handling |
|------|----------|
| Image-only message (no text) | Send image blocks with no text block — Claude handles this |
| Multiple images | Array of image blocks, up to 5 |
| Oversized file (>10 MB) | Skip with log warning, process remaining attachments |
| Download failure (CDN timeout) | Skip failed attachment, send what we have |
| Unsupported file type (PDF, zip) | Silently skip |
| Spoofed content-type (renamed .exe to .png) | Magic bytes detection rejects non-images |
| Gateway unavailable | Attachments dropped, text-only via legacy bridge |
| Text-only message | Backwards compatible — `attachments: []` |
| Session resume after image message | History shows metadata placeholder, not image data |

## What's NOT Built

- PDF extraction or OCR
- TUI attachment support (claude handles files natively)
- Storing image data in message history
- Discord embed or sticker support
- Discord message edit handling (not handled for text either)

## Acceptance Criteria

- [x] Image attachments (jpeg, png, gif, webp) reach Claude and get analyzed
- [x] Image-only messages (no text) are processed, not dropped
- [x] Multiple images in one message work (up to 5)
- [x] Text files injected as text content blocks with filename
- [x] Unsupported file types silently skipped
- [x] Files over 10 MB skipped with log warning
- [x] Media type detected from magic bytes, not extension/header
- [x] Message history stores metadata placeholder, not base64 blobs
- [x] Text-only messages work identically to before (backwards compatible)
- [x] Legacy bridge fallback skips attachments gracefully
- [x] WebSocket max_size configured for large payloads

## Files Changed

| File | Change | Size |
|------|--------|------|
| `gateway/protocol.py` | Add `attachments` field to `UserMessage` | S |
| `gateway/claude_pool.py` | `send_message` builds content blocks from attachments | S |
| `gateway/router.py` | Pass attachments through, store metadata in history | S |
| `bot/gateway_client.py` | Accept and transmit attachments | S |
| `bot/main.py` | Download attachments, allow image-only messages | M |
| `gateway/server.py` | Increase WebSocket `max_size` | S |

## Implementation Order

1. `gateway/protocol.py` — add `attachments` field
2. `gateway/claude_pool.py` — extend `send_message` to build content blocks
3. `gateway/router.py` — pass attachments through, store metadata
4. `bot/gateway_client.py` — accept attachments param
5. `gateway/server.py` — increase max_size
6. `bot/main.py` — download, encode, send attachments

Bottom-up: change the innermost layer first (claude_pool), then work outward to the Discord bot. Each layer can be tested independently.

## References

- [Agent SDK: Streaming vs Single Mode](https://platform.claude.com/docs/en/agent-sdk/streaming-vs-single-mode) — confirms image content blocks in stream-json input
- `gateway/claude_pool.py:80-98` — current send_message with content blocks array
- `bot/main.py:216-281` — current on_message handler
- `bot/gateway_client.py:100-140` — current gateway client send_message
- GitHub issues [#11936](https://github.com/anthropics/claude-code/issues/11936), [#7088](https://github.com/anthropics/claude-code/issues/7088) — media type mismatch bugs in Claude Code
