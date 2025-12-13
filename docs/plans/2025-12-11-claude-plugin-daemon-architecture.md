# Claude Plugin Daemon Architecture

## Problem

The current Claude plugin uses synchronous hooks that fire as separate Python processes for each event. This causes several issues:

1. **Image timing**: When a user pastes an image, the image data isn't written to the session file until AFTER the `UserPromptSubmit` hook returns. This means we can't attach images to turn inputs where they belong.

2. **Process overhead**: Starting a new Python process for each hook event is expensive.

3. **Missed events**: If Claude Code is force-quit, `Stop` and `SessionEnd` hooks may never fire, leaving traces incomplete.

## Solution

Replace the synchronous hook-per-event model with a **daemon architecture**:

1. **Hooks become thin relays**: Check if daemon is running, start it if not, send event payload via Unix socket
2. **Daemon tails session file**: Creates Weave traces reactively as content appears
3. **Images captured correctly**: Daemon sees images in session file after hook returns

## Architecture Overview

```
Claude Code → Hook → Unix Socket → Daemon → Weave API
                                      ↑
                          Session File (tail)
```

**Components:**

1. **Hook script** (`hook.py`): Lightweight, invoked by Claude Code. Checks if daemon is running, starts it if needed, sends event payloads via Unix socket.

2. **Daemon process** (`daemon.py`): Long-running per-session process. Tails session file, creates Weave traces reactively, receives hook events via socket.

3. **State file** (`~/.cache/weave/claude-plugin.json`): Persists session metadata, Weave call IDs, daemon PID, and processing position for recovery.

## State File Structure

```json
{
  "sessions": {
    "session-uuid-1": {
      "project": "entity/project",
      "entity": "wandb_fc",
      "session_call_id": "019b0fb7-90ec-...",
      "trace_id": "019b0fb7-90ec-...",
      "trace_url": "https://wandb.ai/entity/project/weave/traces/...",
      "turn_call_id": "019b0fb8-1234-...",
      "turn_number": 5,
      "total_tool_calls": 23,
      "tool_counts": {"Read": 8, "Grep": 6, "Edit": 5, "Bash": 4},
      "daemon_pid": 12345,
      "last_processed_line": 150,
      "transcript_path": "/path/to/session.jsonl",
      "cwd": "/Users/vanpelt/Development/weave",
      "last_updated": "2025-12-11T10:30:00Z"
    }
  },
  "cwds": {
    "/Users/vanpelt/Development/weave": ["session-uuid-1"]
  }
}
```

**New fields:**
- `trace_url`: Cached trace URL for returning in `additionalContext`
- `daemon_pid`: PID of the daemon process for this session
- `last_processed_line`: Line number in session file we've processed up to
- `transcript_path`: Path to the session JSONL file

## Hook Behavior

The hook script becomes thin - its job is to relay events to the daemon:

### SessionStart

1. Write initial state (session_id, transcript_path, cwd)
2. Start daemon (if not running)
3. Send `SessionStart` payload to daemon
4. Return (no additionalContext)

### UserPromptSubmit

1. Ensure daemon running (start if needed)
2. Send payload to daemon
3. **Synchronous wait** for response (first turn only - to get trace URL)
4. Return `additionalContext` with trace URL (from daemon response or cached in state)

### Stop / SubagentStop

1. Ensure daemon running
2. Send payload to daemon (contains transcript_path for subagents)
3. Return immediately (no response needed)

### SessionEnd

1. Send payload to daemon
2. Daemon finishes session call, cleans up, exits
3. Hook cleans up state entry

## Daemon Behavior

### Startup

1. Read state file to get `transcript_path`, `session_call_id`, `last_processed_line`
2. Initialize Weave with project from state
3. Create Unix socket at `~/.cache/weave/daemon-{session_id}.sock`
4. Start file tailer at `last_processed_line` offset
5. Start inactivity timer (10 minutes)

### File Tailing Loop

1. Watch session file for new lines
2. Parse each new JSONL line
3. On **user message**: Create `claude_code.turn` call with user text + images (images now available!)
4. On **tool call**: Create `claude_code.tool.*` call as child of current turn
5. On **assistant response**: Buffer for turn completion
6. Update `last_processed_line` in state periodically

### Socket Event Handling

| Event | Action |
|-------|--------|
| `SessionStart` | Create `claude_code.session` call, store `trace_url` in state, respond with URL |
| `UserPromptSubmit` | If no session call yet, create it synchronously and respond with URL. Otherwise just ACK. |
| `Stop` | Finish current turn call with full output (response, usage, tool counts) |
| `SubagentStop` | Parse subagent transcript from payload's `transcript_path`, create subagent trace |
| `SessionEnd` | Finish session call, cleanup state, exit daemon |

### Shutdown Triggers

- `SessionEnd` hook received
- 10-minute inactivity timeout (no hooks, no file changes)
- Clean exit: remove socket file, update state to clear `daemon_pid`

**Important**: On timeout, the daemon exits but does NOT finish the session call. The session call only gets finished on `SessionEnd` hook.

## Trace Creation Timeline

```
Time    Event                           Daemon Action
─────   ─────                           ─────────────
T+0     User types prompt (with image)
T+1     UserPromptSubmit hook fires     Create session call (sync), return URL
T+2     Hook returns additionalContext
T+3     Claude writes to session file   Daemon sees user message + image
T+4                                     Create turn call with image in input
T+5     Claude calls Read tool          Daemon sees tool call in file
T+6                                     Create tool call as child of turn
T+7     Claude finishes response
T+8     Stop hook fires                 Finish turn call with response/usage
```

**Key insight**: Images are attached to turn input at T+4, after the hook returns (T+2), because the daemon reads them from the session file.

## Process Management

### Checking Daemon Liveness

1. Try connecting to socket `~/.cache/weave/daemon-{session_id}.sock`
2. If connection succeeds → daemon running
3. If connection fails → check if `daemon_pid` process exists
4. If process dead → clean up socket file, start new daemon

### Starting Daemon

```python
subprocess.Popen(
    [sys.executable, "-m", "weave.integrations.claude_plugin.daemon", session_id],
    start_new_session=True,  # Detach from parent
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```

### Socket Protocol

Simple JSON-over-socket:

```python
# Hook sends:
{"event": "UserPromptSubmit", "payload": {...}}

# Daemon responds:
{"status": "ok", "trace_url": "https://..."}  # or just {"status": "ok"}
```

## Error Handling & Edge Cases

### Daemon crash/kill

- Hook tries to connect → fails
- Checks `daemon_pid` in state → process doesn't exist
- Cleans up stale socket file
- Starts fresh daemon
- Daemon resumes from `last_processed_line`

### Interrupted turns (user presses Escape)

- No `Stop` hook fires
- Daemon sees next user message appear in file
- Detects previous turn never finished (has open turn call)
- Finishes previous turn with `interrupted: true`
- Creates new turn call

### Session file edge cases

- Files are append-only per session (no rotation)
- If file smaller than `last_processed_line` (unlikely), reset to 0 and reprocess
- Weave calls tracked by ID in state - no duplicate creation

### Multiple Claude windows

- Each session has its own daemon (by session_id)
- Separate socket files: `daemon-{session_id}.sock`
- No interference between sessions

### Daemon timeout during long idle

- User walks away, daemon times out after 10 min
- User returns, types new prompt
- `UserPromptSubmit` hook fires → starts new daemon
- Daemon reads state, resumes tailing from `last_processed_line`
- `trace_url` still in state for `additionalContext`

## Implementation Plan

### New files

- `daemon.py`: Main daemon process (socket server, file tailer, Weave trace creation)
- `socket_client.py`: Helper for hooks to communicate with daemon

### Modified files

- `hook.py`: Simplify to just relay events to daemon
- `state.py`: Add `daemon_pid`, `trace_url`, `last_processed_line`, `transcript_path` fields
- `handlers.py`: Move trace creation logic to daemon (most code migrates)

### Reused as-is

- `session_parser.py`: Already parses session JSONL files
- `diff_view.py`: Generates HTML diffs
- `utils.py`: Helper functions
- `session_title.py`: Ollama summarization

### Migration

- No state file format change needed (just new optional fields)
- Old state entries work fine (daemon starts fresh if no `last_processed_line`)

## Benefits

1. **Images work correctly**: Attached to turn input after session file is written
2. **Lower latency**: Daemon already running, no Python startup per hook
3. **Better recovery**: Daemon resumes from last position on restart
4. **Cleaner separation**: Hooks are thin relays, daemon owns trace logic
5. **Graceful degradation**: Timeout doesn't lose data, just pauses tracing
