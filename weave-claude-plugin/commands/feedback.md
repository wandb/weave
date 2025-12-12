---
description: Rate your session: 1=great, 4=crap, also accepts optional note.
---

Collect feedback about this Claude Code session and send it to Weave.

## Arguments

This command accepts optional arguments: `/weave:feedback [rating] [note...]`

- **rating**: `1`, `2`, `3`, `4` OR any emoji (e.g., `🤩`, `👍`)
  - `1` or `🤩` = Totally stoked
  - `2` or `😊` = Pleased
  - `3` or `😕` = Displeased
  - `4` or `🤮` = Really disappointed
- **note**: Any text after the rating becomes the note

**Examples:**
- `/weave:feedback` - Interactive mode (asks for rating and note)
- `/weave:feedback 1` - Quick rating, no note
- `/weave:feedback 🤩 This session was amazing!` - Rating with note
- `/weave:feedback 2 Good progress today` - Rating 2 with note

## Processing Logic

### If arguments were provided:

1. **Parse the first argument as rating:**
   - If it's `1`, `2`, `3`, or `4`: map to emoji (🤩, 😊, 😕, 🤮)
   - If it's already an emoji: use it directly
   - If invalid: show error "Invalid rating. Use 1-4 or an emoji." but continue to interactive mode

2. **If rating is valid:**
   - If there's remaining text after the rating, use it as the note
   - If no note text was provided, set note to null (don't ask for one)
   - Skip to "Send Feedback" step

### If no arguments (or invalid arguments):

**Step 1: Ask for Rating**

Use AskUserQuestion to get the rating:

Question: "How is this session going?"
Header: "Rating"
Options:
1. Label: "Totally stoked", Description: "Everything is amazing"
2. Label: "Pleased", Description: "Going well"
3. Label: "Displeased", Description: "Having some issues"
4. Label: "Really disappointed", Description: "Not working for me"

Map the selection to emoji:
- "Totally stoked" -> 🤩
- "Pleased" -> 😊
- "Displeased" -> 😕
- "Really disappointed" -> 🤮

**Step 2: Ask for Note**

Use AskUserQuestion to collect an optional note:

Question: "Any feedback you'd like to share?"
Header: "Note"
Options:
1. Label: "Skip", Description: "No additional comments"

If they provide text via "Other", use that as the note.
If they select "Skip", set note to null.

## Send Feedback

First, find the Weave session_id from the conversation context. Look for a system reminder containing "Weave session_id:" - extract that UUID.

Then run this command:

```bash
python -m weave.integrations.claude_plugin.feedback "<SESSION_ID>" "<EMOJI>" "<NOTE>"
```

If the python command fails (weave not installed), fall back to uvx:

```bash
uvx --from "weave>=0.52.23" python -m weave.integrations.claude_plugin.feedback "<SESSION_ID>" "<EMOJI>" "<NOTE>"
```

- Replace `<SESSION_ID>` with the UUID from "Weave session_id:" in context
- Replace `<EMOJI>` with the emoji (🤩, 😊, 😕, 🤮, or custom)
- Replace `<NOTE>` with the note text, or omit the argument entirely if no note

**Examples:**

With note:
```bash
python -m weave.integrations.claude_plugin.feedback "abc-123-def" "🤩" "Great collaboration!"
```

Without note:
```bash
python -m weave.integrations.claude_plugin.feedback "abc-123-def" "😊"
```

## Confirm

After sending, tell the user: "Thanks for your feedback! Your [emoji] rating has been recorded."
If they included a note, add: "Your note has been saved too."
