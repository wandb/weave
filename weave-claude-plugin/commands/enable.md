---
description: Enable Weave tracing for Claude Code sessions
---

Enable the Weave tracing plugin to record Claude Code sessions to Weave.

## Arguments

This command accepts optional arguments: `/weave:enable [--global]`

- **--global**: Enable globally instead of for this project only

## Processing Logic

1. **Check for --global flag**: If the user provided `--global`, skip to step 4 with global mode.

2. **Check if .claude/settings.json exists**: Run status to check:
   ```bash
   python -m weave.integrations.claude_plugin.config status 2>&1
   ```

   Look for "Local (.claude/settings.json): not set" in the output.

3. **If no local settings file exists**, use AskUserQuestion:

   Question: "No .claude/settings.json found. Create it to enable Weave for this project?"
   Header: "Create file"
   Options:
   1. Label: "Yes, create it", Description: "Create .claude/settings.json with weave.enabled: true"
   2. Label: "Enable globally instead", Description: "Enable in ~/.cache/weave/config.json for all projects"
   3. Label: "Cancel", Description: "Don't enable Weave"

   - If "Yes, create it": Continue to step 4 with local mode
   - If "Enable globally instead": Continue to step 4 with global mode
   - If "Cancel": Say "Weave tracing not enabled." and stop

4. **Enable tracing**:

   For global mode:
   ```bash
   python -m weave.integrations.claude_plugin.config enable --global 2>&1
   ```

   For local mode (default):
   ```bash
   python -m weave.integrations.claude_plugin.config enable 2>&1
   ```

5. **Confirm**:
   - For local: "Weave tracing enabled for this project (.claude/settings.json). Your next session will be traced."
   - For global: "Weave tracing enabled globally. Your next session will be traced."

   If WEAVE_PROJECT is not set, add: "Note: Set WEAVE_PROJECT environment variable to specify the destination project."
