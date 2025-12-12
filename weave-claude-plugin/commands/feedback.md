---
description: Rate your Claude Code session experience with Weave feedback
---

Collect feedback about how this Claude Code session is going and send it to Weave.

## Step 1: Ask for Rating

Use the AskUserQuestion tool to ask the user to rate their session experience. Use these exact options:

Question: "How is this session going?"
Header: "Rating"
Options (in this order):
1. Label: "Totally stoked", Description: "Everything is amazing"
2. Label: "Pleased", Description: "Going well"
3. Label: "Displeased", Description: "Having some issues"
4. Label: "Really disappointed", Description: "Not working for me"

## Step 2: Map Rating to Emoji

Based on the user's selection, map to an emoji:
- "Totally stoked" -> 🤩
- "Pleased" -> 😊
- "Displeased" -> 😕
- "Really disappointed" -> 🤮

## Step 3: Ask for Optional Note

Use AskUserQuestion again to ask if they want to add a note:

Question: "Would you like to add a note explaining your feedback?"
Header: "Note"
Options:
1. Label: "No thanks", Description: "Just submit the rating"
2. Label: "Yes", Description: "I'd like to add some context"

If they select "Yes" or provide text via "Other", capture that as the note.

## Step 4: Send Feedback to Weave

Run this bash command to send the feedback to the Weave daemon:

```bash
echo '{"event": "Feedback", "payload": {"emoji": "<EMOJI>", "note": <NOTE_OR_NULL>}}' | nc -U "${HOME}/.cache/weave/daemon-${CLAUDE_SESSION_ID}.sock"
```

Replace:
- `<EMOJI>` with the mapped emoji (🤩, 😊, 😕, or 🤮)
- `<NOTE_OR_NULL>` with the note string in quotes, or `null` if no note

Example with note:
```bash
echo '{"event": "Feedback", "payload": {"emoji": "🤩", "note": "Claude helped me fix a tricky bug!"}}' | nc -U "${HOME}/.cache/weave/daemon-${CLAUDE_SESSION_ID}.sock"
```

Example without note:
```bash
echo '{"event": "Feedback", "payload": {"emoji": "😊", "note": null}}' | nc -U "${HOME}/.cache/weave/daemon-${CLAUDE_SESSION_ID}.sock"
```

## Step 5: Confirm

After sending, tell the user their feedback has been recorded and thank them.
