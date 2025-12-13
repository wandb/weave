---
description: Teleport a Claude session from another machine to resume work locally.
---

Teleport a Claude Code session from Weave to the current machine. This allows you to start work on system A and seamlessly continue on system B.

## Arguments

This command requires one argument: `/weave:teleport <session_id>`

- **session_id**: The UUID of the session to teleport (required)

**Examples:**
- `/weave:teleport d40a1966-dac0-464d-b81d-ea96d379563d`

## Prerequisites

Before teleporting:
1. You must be in a git repository
2. The repo should be the same as where the original session ran (same git remote)
3. The repo should be in a clean state (no uncommitted changes)

## Processing Logic

### Step 1: Find Weave Project

Look for the WEAVE_PROJECT environment variable or "Weave session_id:" in context to determine the project.

If no project is found, ask the user:

Question: "Which Weave project contains this session?"
Header: "Project"
Options:
1. Label: "Enter project", Description: "Specify entity/project format"

### Step 2: Run Teleport Command

Run this command:

```bash
python -m weave.integrations.claude_plugin.teleport "<SESSION_ID>" "<PROJECT>"
```

If the python command fails (weave not installed), fall back to uvx:

```bash
uvx --from "weave>=0.52.23" python -m weave.integrations.claude_plugin.teleport "<SESSION_ID>" "<PROJECT>"
```

- Replace `<SESSION_ID>` with the session UUID provided by the user
- Replace `<PROJECT>` with the Weave project in "entity/project" format

### Step 3: Handle Errors

If the command fails, display the error message to the user. Common errors:

- **"Session not found"**: The session ID may be wrong or in a different project
- **"Remote mismatch"**: User is in the wrong git repository
- **"Uncommitted changes"**: User needs to commit or stash their changes first
- **"Session still active"**: The session hasn't ended yet on the source machine

### Step 4: Confirm Success

If successful, the command will output:
- Number of files restored
- Path to the session file
- Command to resume the session

Tell the user they can now run `claude --resume <session_id>` to continue their work.

## What Gets Teleported

1. **Session file**: The conversation history (session.jsonl)
2. **File snapshots**: Final state of all files modified/created during the session
3. **Git metadata**: Verification that you're in the right repo/branch

## Safety Checks

The teleport command verifies:
- Git remote matches (same repository)
- No uncommitted changes (clean working tree)
- Session has ended (not still active)

Commit/branch mismatches are warnings, not errors, allowing you to teleport to a different branch if desired.
