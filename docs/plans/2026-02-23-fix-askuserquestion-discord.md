# Fix: AskUserQuestion via Discord Multi-Turn Conversation

## Problem

`AskUserQuestion` is a Claude Code built-in tool that requires an interactive terminal. The bot runs Claude in non-interactive modes (`--print` for direct CLI, `--print --input-format stream-json --output-format stream-json` for the gateway). When Claude tries to use `AskUserQuestion`, it fails with `<error>Answer questions?</error>`.

This breaks the `/life:evening` interactive review, which uses `AskUserQuestion` to ask Scott questions one at a time.

## Approach: Multi-Turn Conversation via System Prompt

Instead of trying to intercept or replace the built-in tool, we:

1. Tell Claude that `AskUserQuestion` is unavailable via the system prompt context
2. Instruct Claude to output questions as regular text and stop after each one
3. Leverage the existing gateway session model for multi-turn conversation
4. Scott's replies in Discord feed back into the same session naturally

This works because:
- The gateway maintains long-running Claude processes with bidirectional streaming
- Sessions persist across messages — Claude remembers the entire conversation
- No new infrastructure, protocols, or MCP servers needed

## Changes

### 1. `bot/context.py` — Add execution context section

In `build_context()`, add a new section before the memory search section:

```python
# Execution context — tool availability and interaction model
parts.append(
    "## Execution Context\n\n"
    "You are running in the ClawCode Discord bot. "
    "The following tool limitations apply:\n\n"
    "- **AskUserQuestion is NOT available** in this environment. "
    "It will fail if called. When you need to ask the user questions "
    "(e.g., during evening reviews, pattern promotion, clarifications), "
    "output each question as regular text in your response, then STOP. "
    "The user will reply in their next Discord message. "
    "Continue the flow in your next response after receiving their answer.\n"
    "- When conducting multi-step interactive flows (like `/life:evening`), "
    "do NOT spawn Task subagents that would use AskUserQuestion (e.g., "
    "`review-conversation`). Instead, conduct the conversation directly — "
    "ask one question at a time as text output.\n"
    "- Format questions clearly. If options exist, list them as numbered choices.\n"
    "- This is a multi-turn conversation. Sessions persist across messages."
)
```

### 2. `gateway/router.py` — Log and relay AskUserQuestion tool_use events (safety net)

In `_route_to_claude`, when iterating over `assistant` event content blocks, add handling for `tool_use` blocks where the tool name is `AskUserQuestion`:

- Extract the question text and options from the tool input
- Format them as readable text
- Send as a `ResponseChunk` to the client (so the user sees the question even if the tool fails)
- Log a warning

This is a belt-and-suspenders measure. The system prompt should prevent Claude from trying AskUserQuestion, but if it does try anyway (e.g., via a subagent that doesn't follow instructions), the user still sees the question.

### 3. No protocol changes needed

The safety net in #2 uses existing `ResponseChunk` messages — no new message types required.

## Flow After Fix

1. Scott types `/life:evening` in Discord
2. Bot sends message to gateway → Claude session
3. Claude runs evening review steps 1-6 (read config, plan, fetch calendar/tasks, etc.)
4. Instead of spawning review-conversation Task agent, Claude outputs:
   "Based on your plan for today, I have a few questions:\n\n**1. You had 'Complete DSci reading' scheduled. How did that go?**"
5. Response streams to Discord. Scott sees the question.
6. Scott replies: "Got through chapter 3, still have 4 and 5 to do"
7. Reply enters same gateway session → Claude continues
8. Claude asks question 2, etc.
9. After all questions answered, Claude generates the review and writes it to disk

## Edge Cases

- **Gateway down, direct CLI fallback**: System prompt still applies. Claude outputs all questions at once in a single response. Less interactive but functional. Scott's reply would include all answers.
- **Schedule-runner**: Reads `data/context.cache` (built by bot). The execution context applies there too. But evening schedule uses `--auto` mode already, so no conflict.
- **CLI usage**: Not affected — CLI doesn't use context.cache, uses its own CLAUDE.md.
- **Subagent ignores instructions**: The safety net in the gateway catches tool_use events and relays questions as text.
