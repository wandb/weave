---
description: Rate your Claude Code session experience with Weave feedback
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

Question: "Any feedback you'd like to share? (optional)"
Header: "Note"
Options:
1. Label: "Skip", Description: "No additional feedback"
2. Label: "Add note", Description: "I have something to share"

If they select "Add note" or provide text via "Other", capture that as the note.
If they select "Skip", set note to null.

## Send Feedback

Run this command to send feedback to Weave:

```bash
"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/feedback.sh" "${CLAUDE_SESSION_ID}" "<EMOJI>" "<NOTE>"
```

- Replace `<EMOJI>` with the emoji (🤩, 😊, 😕, 🤮, or custom)
- Replace `<NOTE>` with the note text, or omit the argument entirely if no note

**Examples:**

With note:
```bash
"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/feedback.sh" "${CLAUDE_SESSION_ID}" "🤩" "Great collaboration on this feature!"
```

Without note:
```bash
"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/feedback.sh" "${CLAUDE_SESSION_ID}" "😊"
```

## Confirm

After sending, tell the user: "Thanks for your feedback! Your [emoji] rating has been recorded."
If they included a note, add: "Your note has been saved too."
