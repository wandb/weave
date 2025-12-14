---
description: Disable Weave tracing for Claude Code sessions
---

Disable the Weave tracing plugin to stop recording sessions.

## Arguments

This command accepts optional arguments: `/weave:disable [--global]`

- **--global**: Disable globally instead of for this project only

## Processing Logic

1. **Check for --global flag**: If the user provided `--global`, use global mode.

2. **Disable tracing**:

   For global mode:
   ```bash
   python -m weave.integrations.claude_plugin.config disable --global 2>&1
   ```

   For local mode (default):
   ```bash
   python -m weave.integrations.claude_plugin.config disable 2>&1
   ```

3. **Confirm**:
   - For local: "Weave tracing disabled for this project (.claude/settings.json)."
   - For global: "Weave tracing disabled globally."

4. **Note**: Mention that local settings take precedence over global. If they want to check the effective state, they can run `/weave:status`.
