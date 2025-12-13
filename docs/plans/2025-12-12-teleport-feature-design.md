# Teleport Feature Design

**Date:** 2025-12-12
**Status:** Approved
**Location:** `weave/integrations/claude_plugin/`

## Overview

Add a "teleport" command to the Claude Code Weave plugin that enables resuming a Claude session from a different machine. This is useful when starting work on system A and wanting to continue on system B.

## User Workflow

```
System A: Working on feature, session traced to Weave
         └── Session ends, all data captured

System B: User wants to continue
         └── /weave:teleport d40a1966-dac0-464d-b81d-ea96d379563d
             ├── Verifies same git repo
             ├── Checks repo is clean
             ├── Checks out correct branch
             ├── Downloads session file
             ├── Restores modified/created files
             └── Outputs: "Run: claude --resume {SESSION_ID}"
```

## Data Capture Changes

### Root Trace Output (SessionEnd)

```python
session_output = {
    # Existing fields
    "turn_count": 5,
    "tool_call_count": 42,
    "usage": {...},
    "end_reason": "user_exit",

    # NEW: Git metadata for teleport verification
    "git": {
        "remote": "git@github.com:wandb/weave.git",
        "branch": "feature/teleport",
        "commit": "abc123def456789...",
    },

    # ENHANCED: file_snapshots includes ALL files (final state)
    "file_snapshots": {
        "session.jsonl": Content(...),           # existing
        "src/handlers.py": Content(...),         # modified file - final state
        "src/teleport.py": Content(...),         # created file - final state
        "tests/test_teleport.py": Content(...),  # created file
    }
}
```

### File Identification

1. **Modified files**: Collect unique file paths from all turns' `file_backups`
2. **Created files**: Scan all Write tool calls, filter to paths not in backups

At SessionEnd, read current disk content for each file and store as Content.

## Teleport Command

### Usage

```
/weave:teleport <session_id>
```

### Command Flow

```
1. FETCH session from Weave API
   └── GET call by session_id, extract git metadata + file_snapshots

2. VERIFY git state
   ├── Check cwd is a git repo
   ├── Check remote matches session's git.remote (normalize URLs)
   ├── Check repo is clean (no uncommitted changes)
   └── Warn if current commit != session's git.commit

3. CHECKOUT branch
   ├── If on wrong branch: offer to checkout session's git.branch
   └── If branch doesn't exist locally: fetch and checkout

4. DOWNLOAD session file
   └── Write to ~/.claude/projects/{path-encoded-cwd}/{SESSION_ID}.jsonl

5. RESTORE files to repo
   └── For each file in file_snapshots (except session.jsonl):
       write Content to {cwd}/{relative_path}

6. OUTPUT resume command
   └── "Run: claude --resume {SESSION_ID}"
```

### Error Handling

| Condition | Response |
|-----------|----------|
| Wrong repo | "Error: Remote mismatch. Expected {remote}, got {actual}" |
| Dirty repo | "Error: Uncommitted changes. Commit or stash first." |
| Missing commit | "Warning: Commit {sha} not found. You may be behind." |
| Session still active | "Error: Session {id} is still active. Wait for it to end." |
| Large/truncated files | "Warning: Some files may be truncated due to size limits." |

## Implementation Changes

### Files to Modify

| File | Changes |
|------|---------|
| `handlers.py` | Add git metadata capture, enhance SessionEnd to capture final file states |
| `session_parser.py` | Add `get_created_files()` method to extract Write tool file paths |
| `utils.py` | Add `get_git_info()` helper |
| `feedback.py` | Add `/weave:teleport` command registration |

### New File

| File | Purpose |
|------|---------|
| `teleport.py` | Core teleport logic: fetch session, verify git, restore files |

### Key Code Additions

#### utils.py

```python
def get_git_info(cwd: str) -> dict[str, str] | None:
    """Get git remote, branch, commit for a directory.

    Returns:
        Dict with 'remote', 'branch', 'commit' keys, or None if not a git repo
    """
    # git remote get-url origin
    # git branch --show-current
    # git rev-parse HEAD
```

#### session_parser.py

```python
# New method on Session class
def get_created_files(self) -> set[str]:
    """Get file paths created via Write tool (no prior backup)."""
    backed_up = {fb.file_path for turn in self.turns for fb in turn.file_backups}
    created = set()
    for turn in self.turns:
        for tc in turn.all_tool_calls():
            if tc.name == "Write":
                path = tc.input.get("file_path", "")
                if path and path not in backed_up:
                    created.add(path)
    return created
```

#### teleport.py

```python
def fetch_session(session_id: str) -> dict:
    """Fetch session call data from Weave by session_id."""

def verify_git_state(expected: dict, cwd: str) -> list[str]:
    """Verify git state matches session. Returns list of warnings/errors."""

def restore_files(file_snapshots: dict, cwd: str) -> int:
    """Restore files to repo. Returns count of files restored."""

def teleport(session_id: str, cwd: str) -> str:
    """Main teleport entry point. Returns status message."""
```

## Edge Cases

1. **Session still active**: Check for `end_reason` in output before allowing teleport
2. **Large files**: Content objects have size limits; warn user if files appear truncated
3. **Binary files**: Content handles binary data; should work but needs testing

## Future Enhancements (Out of Scope)

- **Undo support**: Store files with content-addressed hashes to recreate Claude's file-history structure
- **Partial teleport**: Restore only specific files or up to a specific turn
- **Conflict resolution**: Handle case where local files differ from session state
