# Claude Plugin State Redesign

## Problem

The current Claude plugin stores state files in `~/.claude/weave-state/{session_id}.json`, creating one file per session. This directory grows unbounded over time since cleanup only happens on explicit `SessionEnd` events (which may not fire if a user force-quits or the session is abandoned).

## Solution

Consolidate to a single state file at `~/.cache/weave/claude-plugin.json` with:
- Automatic cleanup of entries older than 30 days
- File locking for concurrent hook access
- A directory index for quick lookups by working directory

## State File Structure

```json
{
  "sessions": {
    "session-uuid-1": {
      "project": "wandb_fc/claude-code-plugin-test",
      "session_call_id": "019b0fb7-90ec-...",
      "trace_id": "019b0fb7-90ec-...",
      "turn_call_id": "019b0fb8-1234-...",
      "turn_number": 5,
      "total_tool_calls": 23,
      "tool_counts": {"Read": 8, "Grep": 6, "Edit": 5, "Bash": 4},
      "last_updated": "2025-12-11T10:30:00Z"
    }
  },
  "cwds": {
    "/Users/vanpelt/Development/weave": ["session-uuid-1", "session-uuid-3"],
    "/Users/vanpelt/Development/other-project": ["session-uuid-2"]
  }
}
```

### Fields

**Required state** (cannot be derived, must persist):
- `session_call_id`: Weave call ID for the session (root trace)
- `trace_id`: Weave trace ID (shared by all calls in session)
- `turn_call_id`: Current turn's Weave call ID (null between turns)

**Cached for visibility** (derived from transcript, stored for human debugging):
- `project`: Weave project in "entity/project" format
- `turn_number`: Number of turns processed
- `total_tool_calls`: Running count of tool calls
- `tool_counts`: Tool call counts by tool name
- `last_updated`: ISO timestamp of last modification

**Directory index**:
- `cwds`: Mapping of working directory paths to lists of session IDs

## Concurrency Handling

Hooks run in separate processes and can overlap. Use `fcntl.flock()` with a separate lock file:

```python
import fcntl
from pathlib import Path

STATE_FILE = Path.home() / ".cache" / "weave" / "claude-plugin.json"
LOCK_FILE = Path.home() / ".cache" / "weave" / "claude-plugin.lock"

def with_state_lock(fn):
    """Decorator that acquires exclusive lock before state operations."""
    def wrapper(*args, **kwargs):
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCK_FILE, 'w') as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)  # Blocking exclusive lock
            return fn(*args, **kwargs)
    return wrapper
```

The lock is automatically released when the file handle closes.

## Cleanup Strategy

On each write operation, prune entries where `last_updated` is older than 30 days:

```python
from datetime import datetime, timedelta, timezone

RETENTION_DAYS = 30

def cleanup_old_entries(data: dict) -> dict:
    """Remove session entries older than RETENTION_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

    expired_sessions = []
    for session_id, session_data in data.get("sessions", {}).items():
        last_updated = datetime.fromisoformat(session_data["last_updated"])
        if last_updated < cutoff:
            expired_sessions.append(session_id)

    # Remove expired sessions
    for session_id in expired_sessions:
        del data["sessions"][session_id]

    # Clean up cwds index
    for cwd, session_ids in list(data.get("cwds", {}).items()):
        data["cwds"][cwd] = [s for s in session_ids if s not in expired_sessions]
        if not data["cwds"][cwd]:
            del data["cwds"][cwd]

    return data
```

## Migration

On first run with the new code:
1. Check if `~/.claude/weave-state/` directory exists
2. If so, migrate any existing state files to the new format
3. Delete the old directory after successful migration

## Implementation Changes

### `state.py`

Replace `HookState` class with:
- `StateManager` class that handles the consolidated JSON file
- Methods: `load_session()`, `save_session()`, `delete_session()`
- Automatic locking and cleanup on save

### `handlers.py`

Update to use new `StateManager`:
- Derive `turn_number` and tool counts from transcript (source of truth)
- Cache derived values in state for human visibility
- Update `cwds` index when session starts

## Benefits

1. **Bounded growth**: Single file with automatic 30-day cleanup
2. **Human-readable**: `cat ~/.cache/weave/claude-plugin.json` shows all active sessions
3. **Directory lookup**: Quickly see which sessions touched a repo
4. **Simpler cleanup**: No directory of files to manage
5. **Proper location**: `~/.cache` is the standard location for application caches
