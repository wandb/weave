# Claude Code Weave Exporter

Export Claude Code session traces to [Weights & Biases Weave](https://weave-docs.wandb.ai) for observability and analysis.

## Features

- Automatic tracing of Claude Code sessions
- Hierarchical trace structure: Session → Tool Calls → Subagents
- Persistent state management across hook invocations
- Graceful error handling (never fails the hook)

## Installation

### 1. Install the package

```bash
pip install -e path/to/claude_code_exporter
```

Or install from source:

```bash
cd lib/claude_code_exporter
pip install -e .
```

### 2. Enable the plugin in Claude Code

Add the plugin to your Claude Code settings. The plugin directory should be added to your `.claude/plugins/` directory or referenced in your Claude Code configuration.

## Configuration

Configure the exporter using a `.env` file in the plugin directory:

```bash
cp .env.example .env
# Edit .env with your values
```

### Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `CC_WEAVE_PROJECT` | Full project path (entity/project) | - |
| `CC_WEAVE_ENTITY` | W&B entity (if not using CC_WEAVE_PROJECT) | - |
| `CC_WEAVE_PROJECT_NAME` | Project name | `claude-code-traces` |
| `CC_WANDB_API_KEY` | W&B API key for authentication | - |
| `CC_ENABLED` | Enable/disable tracing | `true` |
| `CC_DEBUG` | Enable verbose debug logging | `false` |

### Example .env

```bash
# W&B API key (required)
CC_WANDB_API_KEY=your-api-key-here

# Option 1: Use CC_WEAVE_PROJECT (recommended)
CC_WEAVE_PROJECT=my-team/claude-code-traces

# Option 2: Use separate entity and project
# CC_WEAVE_ENTITY=my-team
# CC_WEAVE_PROJECT_NAME=claude-code-traces
```

## Trace Structure

The exporter creates a turn-based hierarchical trace structure:

```
Claude Code Session (root trace)
├── Turn #1 (user_message → agent_response)
│   ├── Tool: Read
│   └── Tool: Write
├── Turn #2 (user_message → agent_response)
│   ├── Tool: Bash
│   ├── Subagent: Explore
│   │   ├── Tool: Glob
│   │   └── Tool: Grep
│   └── Tool: Edit
└── Turn #3 (user_message → agent_response)
```

Each turn captures:
- **Input**: The user's message/prompt
- **Output**: The agent's response
- **Children**: All tool calls and subagents within that turn

### Events Captured

| Event | Trace Action |
|-------|--------------|
| SessionStart | Creates root trace with session metadata |
| UserPromptSubmit | Starts a new turn span with user message as input |
| PreToolUse | Creates child span for tool call (within current turn) |
| PostToolUse | Finishes child span with output/error |
| SubagentStart | Creates nested span, pushes to stack |
| SubagentStop | Finishes nested span, pops from stack |
| Stop | Finishes current turn span with agent response as output |
| SessionEnd | Finishes root trace, cleans up state |

## Viewing Traces

After running Claude Code with the exporter enabled:

1. Go to [wandb.ai](https://wandb.ai)
2. Navigate to your project
3. Click on "Weave" in the sidebar
4. View your Claude Code session traces

## State Management

The exporter maintains state between hook invocations in `~/.claude_code_weave/state_<session_id>.json`. This allows:

- Tracking parent-child relationships across hooks
- Managing the subagent nesting stack
- Correlating PreToolUse with PostToolUse events

State files are automatically cleaned up when sessions end.

## Troubleshooting

### Traces not appearing

1. Ensure `.env` file exists in the plugin directory (copy from `.env.example`)
2. Check that `CC_WANDB_API_KEY` is set correctly in `.env`
3. Verify `CC_WEAVE_PROJECT` or `CC_WEAVE_ENTITY`/`CC_WEAVE_PROJECT_NAME` are configured
4. Ensure `CC_ENABLED` is not set to `false`
5. Check stderr output for error messages

### Debugging

Enable verbose logging by setting `CC_DEBUG=true` in your `.env` file:

```bash
CC_DEBUG=true
```

With debug mode enabled, you'll see:
- Session start/end events
- Each tool call start/finish
- Subagent start/stop events
- Full stack traces on errors

All output goes to stderr and won't interfere with Claude Code.

## License

Apache-2.0. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see the [Weave repository](https://github.com/wandb/weave) for contribution guidelines.
