# Claude Code Weave Plugin

A real-time tracing integration that captures Claude Code sessions and logs them to Weave for analysis, debugging, and observability.

## Architecture Overview

The plugin uses a **two-tier architecture** designed for minimal latency and high reliability:

```
Claude Code ──────────────────────────────────────────────────────────────────
    │
    ├── SessionStart ──┐
    ├── UserPromptSubmit ───┐
    ├── Stop ───────────────┼──▶ hook.py ──▶ Unix Socket ──▶ daemon.py
    ├── SubagentStop ───────┤                                    │
    └── SessionEnd ─────────┘                                    │
                                                                 ▼
                                                            Weave Traces
                                                            ┌─────────────────┐
                                                            │ Session         │
                                                            │ ├── Turn 1      │
                                                            │ │   ├── Tool 1  │
                                                            │ │   └── Tool 2  │
                                                            │ ├── Turn 2      │
                                                            │ └── Subagent    │
                                                            │     └── Turns   │
                                                            └─────────────────┘
```

1. **Hook Layer** (`hook.py`) - Fast, stateless entry point invoked by Claude Code hooks. Relays events to the daemon via Unix socket and returns trace URLs.

2. **Daemon Layer** (`daemon.py`) - Long-lived background process that processes events, tails the session transcript file, and creates Weave traces reactively.

## File Overview

### Core (`core/`)
| File | Purpose |
|------|---------|
| `hook.py` | Entry point for Claude Code hook invocations |
| `daemon.py` | Background process that creates Weave traces |
| `socket_client.py` | Unix socket IPC between hook and daemon |
| `state.py` | Persists state across process invocations |

### Session (`session/`)
| File | Purpose |
|------|---------|
| `session_parser.py` | Parses Claude's JSONL transcript files |
| `session_processor.py` | Factory for creating Weave traces from sessions |
| `session_importer.py` | Batch import of session files |
| `session_title.py` | Generates session names via Claude API |

### Views (`views/`)
| File | Purpose |
|------|---------|
| `diff_view.py` | Generates GitHub-style HTML diffs |
| `diff_utils.py` | Diff calculation utilities |
| `cli_output.py` | Rich CLI output formatting |
| `feedback.py` | CLI for sending session feedback |

### Top-level
| File | Purpose |
|------|---------|
| `config.py` | Global and local configuration management |
| `credentials.py` | Retrieves Claude Code OAuth credentials |
| `constants.py` | Shared constants (timeouts, paths, etc.) |
| `utils.py` | Shared utilities (truncation, tool buffering, display names) |

## Configuration

### Required Environment Variables

```bash
WEAVE_PROJECT="entity/project"  # Weave project in entity/project format
```

### Optional Environment Variables

```bash
WEAVE_HOOK_DISABLED=1  # Disable all tracing
DEBUG=1                # Enable debug logging to /tmp/weave-claude-*.log
```

## How It Works

### Event Flow

1. **SessionStart**: Hook receives session start, initializes state file with session ID and transcript path.

2. **UserPromptSubmit**: Hook ensures daemon is running, sends event. On first prompt, daemon creates the session call and returns trace URL.

3. **File Tailing**: Daemon polls the session transcript file every 500ms, creating turn and tool call traces as data appears.

4. **Stop**: When a turn completes, the Stop event triggers final processing of the transcript and finishes the current turn call.

5. **SubagentStop**: When Claude spawns a subagent (Task tool), the SubagentStop event creates a nested trace hierarchy for the subagent's work.

6. **SessionEnd**: Finishes the session call, cleans up state, and shuts down the daemon.

### Trace Hierarchy

```
Session Call (claude_code.session)
├── Turn Call 1 (claude_code.turn)
│   ├── Tool Call 1 (claude_code.tool.{name})
│   ├── Tool Call 2
│   ├── Question Call (claude_code.question)  ← AskUserQuestion tool
│   ├── SubAgent Call (claude_code.subagent)  ← spawned by Task tool
│   │   ├── Tool Call 1 (flat structure for simple subagents)
│   │   └── Tool Call 2
│   └── ...
├── Turn Call 2
│   └── ...
```

**Subagent Structure:**
- Subagents are attached to the **turn** that spawned them (via Task tool), not the session
- **Simple subagents** (single turn): Tool calls logged directly under subagent (flat)
- **Complex subagents** (multiple turns/user interaction): Turn hierarchy preserved

### Question/Answer Context Tracking

When Claude asks questions (via `AskUserQuestion` tool or ending a turn with a question), the plugin tracks this context to improve trace readability:

**AskUserQuestion Tool:**
- Creates a `claude_code.question` sub-call under the current turn
- Input contains the structured questions and options
- Output contains the user's selected answers
- Display name shows the question text (e.g., "Q: How is this session going?")

**Text-based Questions:**
- Detected when assistant output ends with "?"
- Stored as `ends_with_question` in turn output
- Next turn includes `in_response_to` in inputs with the question text
- Helps users understand what the user's answer is responding to

```
Turn 1 Output:
├── response: "...Which option do you prefer?"
└── ends_with_question: "Which option do you prefer?"

Turn 2 Input:
├── user_message: "Let's go with Option A"
└── in_response_to: "Which option do you prefer?"
```

### File Change Tracking

When Claude edits files, the plugin captures file snapshots and generates visual diffs:

**File Backups:**
- Claude Code maintains file backups in `~/.claude/file-history/{session_id}/`
- When a turn completes, the plugin loads any file backups associated with that turn
- Backups are stored in the turn output as `file_snapshots` (dict of file path → Content)

**Diff View:**
- Each turn with file changes gets a `file_changes` HTML view attached
- The diff shows GitHub-style visual comparison between:
  - **Before**: The file backup (state before Claude's edit)
  - **After**: Current file on disk (state after Claude's edit)
- Syntax highlighting based on file extension
- Accessible via the "Summary" tab in the Weave UI

```
Turn Output:
├── model: "claude-sonnet-4-..."
├── usage: {input_tokens: ..., output_tokens: ...}
├── response: "I've updated the file..."
├── file_snapshots: {"src/app.py": <Content>}  ← backup before edit
└── [file_changes view]: <HTML diff>           ← visual diff
```

### State Persistence

State is persisted to `~/.cache/weave/claude-plugin.json` with file locking for concurrency:

```json
{
  "sessions": {
    "session-id": {
      "project": "entity/project",
      "session_call_id": "weave-call-id",
      "trace_url": "https://weave.wandb.ai/...",
      "turn_call_id": "current-turn-id",
      "turn_number": 3,
      "daemon_pid": 12345,
      "last_processed_line": 42,
      "transcript_path": "/path/to/session.jsonl"
    }
  }
}
```

## Key Design Decisions

### Two-Tier Architecture
- **Hooks** are fast and stateless - they execute as separate processes for each Claude Code event
- **Daemon** is persistent - maintains state, handles I/O, creates traces without blocking hooks

### Unix Sockets for IPC
- Faster than HTTP
- No port binding conflicts
- Per-session isolation: `~/.cache/weave/daemon-{session_id}.sock`

### Reactive Trace Creation
- Traces created as transcript data becomes available
- File tailing at 500ms intervals
- Turn calls finished at Stop event time

### Warmup Subagent Handling
- Claude Code fires "warmup" subagents behind the scenes to warm the prompt cache
- These fire before the actual user prompt arrives
- Session title generation skips warmup events and finds the first real user prompt from the transcript

### Graceful Degradation
- Session title generation has multiple fallbacks (Claude API → Ollama → truncated prompt)
- Tool display names handle missing input gracefully
- Inactivity timeout (10 minutes) prevents daemon resource leaks

## Development

### Running the Hook Manually

```bash
# Set required environment
export WEAVE_PROJECT="your-entity/your-project"

# Hook is invoked by Claude Code automatically via hook config
python -m weave.integrations.claude_plugin
```

### Debug Logging

Set `DEBUG=1` to enable logging:
- Hook logs: `/tmp/weave-claude-debug.log`
- Daemon logs: `/tmp/weave-claude-daemon-{session_id}.log`

### Socket Locations

- Active sockets: `~/.cache/weave/daemon-{session_id}.sock`
- State file: `~/.cache/weave/claude-plugin.json`
- Lock file: `~/.cache/weave/claude-plugin.lock`

## Transcript Format

Claude Code writes session transcripts as JSONL files:

```jsonl
{"type": "user", "uuid": "...", "timestamp": "...", "message": {"content": "..."}}
{"type": "assistant", "uuid": "...", "timestamp": "...", "message": {"content": [...], "model": "...", "usage": {...}}}
{"type": "file-history-snapshot", "snapshot": {"messageId": "...", "trackedFileBackups": {...}}}
```

The `session_parser.py` module parses these into structured `Turn`, `Session`, `ToolCall`, and `FileBackup` objects.

## Error Handling

- **Socket failures**: Hook falls back gracefully if daemon is unreachable
- **Stale sockets**: Automatically cleaned up on reconnection attempts
- **State corruption**: Automatic lock timeout, atomic writes
- **Parse errors**: Invalid JSON lines skipped, incomplete messages handled
