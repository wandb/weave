# Weave Feedback Slash Command Design

**Date:** 2025-12-12
**Status:** Approved

## Overview

Add a `/weave:feedback` slash command to the weave-claude-plugin that allows users to rate their Claude Code session experience. Feedback is recorded to the Weave trace as reactions and optional notes on the session call.

## User Experience

1. User types `/weave:feedback`
2. Claude prompts for a 4-point rating using `AskUserQuestion`:
   - 🤩 Totally stoked - everything is amazing
   - 😊 Pleased - going well
   - 😕 Displeased - having some issues
   - 🤮 Really disappointed - not working for me
3. Claude asks if they'd like to add an optional note
4. Feedback is sent to the daemon and recorded on the session call
5. Claude confirms feedback was recorded

## Architecture

### Data Flow

```
/weave:feedback command
       │
       ▼
Claude uses AskUserQuestion tool
       │
       ▼
Claude sends JSON via Unix socket
       │
       ▼
Daemon _handle_feedback()
       │
       ▼
weave_client.get_call(session_call_id)
       │
       ▼
call.feedback.add_reaction(emoji)
call.feedback.add_note(note)  # if provided
```

### File Changes

**New file: `weave-claude-plugin/commands/feedback.md`**

```markdown
---
description: Rate your Claude Code session experience with Weave feedback
---

Use the AskUserQuestion tool to collect feedback about how this session is going.

First, ask for a rating with these 4 options:
- 🤩 Totally stoked - everything is amazing
- 😊 Pleased - going well
- 😕 Displeased - having some issues
- 🤮 Really disappointed - not working for me

Then ask if they'd like to add an optional note explaining their feedback.

Finally, run this command to send the feedback to Weave:
```bash
echo '{"event": "Feedback", "payload": {"emoji": "<selected_emoji>", "note": "<optional_note_or_null>"}}' | nc -U /tmp/weave-claude-<session_id>.sock
```

The session_id can be found in the CLAUDE_SESSION_ID environment variable.
```

**Modified file: `weave/integrations/claude_plugin/daemon.py`**

Add new event handler:

```python
async def _handle_event(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    # ... existing handlers ...
    elif event == "Feedback":
        return await self._handle_feedback(payload)
    # ...

async def _handle_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
    """Handle Feedback - add reaction/note to session call."""
    if not self.weave_client or not self.session_call_id:
        return {"status": "error", "message": "No active session"}

    emoji = payload.get("emoji")
    note = payload.get("note")

    # Get the session call
    session_call = self.weave_client.get_call(self.session_call_id)

    # Add reaction
    if emoji:
        session_call.feedback.add_reaction(emoji, creator="user")

    # Add note if provided
    if note:
        session_call.feedback.add_note(note, creator="user")

    logger.info(f"Added feedback to session: emoji={emoji}, has_note={bool(note)}")
    return {"status": "ok"}
```

## Design Decisions

1. **Socket-based communication** - Reuses existing daemon infrastructure rather than making direct API calls from the command
2. **Session-level feedback** - Attaches to the root session call since we're asking "how is the session going overall"
3. **4-point emoji scale** - Face expressions (🤩😊😕🤮) are intuitive for rating experience quality
4. **Optional note** - Allows users to provide context without requiring it

## Summary of Changes

| File | Change |
|------|--------|
| `weave-claude-plugin/commands/feedback.md` | New slash command |
| `weave/integrations/claude_plugin/daemon.py` | Add `_handle_feedback` handler |
