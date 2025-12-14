---
description: Show Weave tracing plugin status
---

Show whether Weave tracing is enabled or disabled.

## Processing Logic

1. **Get status**:
   ```bash
   python -m weave.integrations.claude_plugin.config status 2>&1
   ```

2. **Display the output** directly to the user. The output shows:
   - Global setting (enabled/disabled) - stored in ~/.cache/weave/config.json
   - Local setting if present in .claude/settings.json
   - Effective state for current directory (what will actually be used)
   - Current WEAVE_PROJECT value

3. **Additional context**:
   - If effective is "disabled", mention: "Run /weave:enable to enable tracing for this project."
   - If effective is "enabled" but project is "not set", mention: "Set WEAVE_PROJECT environment variable to specify the destination project."
   - Explain that local settings take precedence over global settings.
