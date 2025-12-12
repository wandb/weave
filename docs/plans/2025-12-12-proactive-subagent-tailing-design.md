# Proactive Subagent File Tailing

**Date:** 2025-12-12
**Status:** Design Complete
**Author:** Claude + Human collaboration

## Problem Statement

Currently, subagent traces are only created when the `SubagentStop` hook fires. This means users see no activity in Weave while a subagent is running - all tool calls appear at once when the subagent completes.

For long-running subagents, this creates a poor user experience. Users want to see subagent progress in real-time.

## Goal

**Live progress visibility** - Show subagent tool calls in Weave as they happen, not all at once when SubagentStop fires.

## Design Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Trace creation | Eager | Create subagent call as soon as file is found, update display name later if needed |
| File scanning | Piggyback on existing 500ms poll | No new timers/dependencies, proven mechanism, acceptable latency |
| Race handling | Hybrid | SubagentStop adapts - fast path if tailing, fallback to full processing if not |
| Data structure | Full lifecycle tracking | Single place for detection → tailing → completion state |
| Detection timeout | 10 seconds | File should appear within 1-2s; 10s handles slow starts |
| File matching | ctime + sessionId | Filter by creation time (cheap), verify sessionId matches parent (reliable) |

## Data Structures

```python
@dataclass
class SubagentTracker:
    """Tracks a subagent through its lifecycle: pending → tailing → finished."""

    # Set at detection time (Task tool with subagent_type)
    tool_use_id: str
    turn_call_id: str
    detected_at: datetime
    parent_session_id: str

    # Set once file is found and matched
    agent_id: str | None = None
    transcript_path: Path | None = None
    subagent_call_id: str | None = None
    last_processed_line: int = 0

    @property
    def is_tailing(self) -> bool:
        """True if we've found the file and started tailing."""
        return self.subagent_call_id is not None
```

**Daemon state:**
```python
class WeaveDaemon:
    # Primary index: tool_use_id (known at detection)
    _subagent_trackers: dict[str, SubagentTracker] = {}

    # Secondary index: agent_id (known once file found, for SubagentStop lookup)
    _subagent_by_agent_id: dict[str, SubagentTracker] = {}
```

## Algorithm

### Phase 1: Detection

When processing the parent session transcript, detect Task tools with `subagent_type`:

```python
if tool_name == "Task" and tool_input.get("subagent_type"):
    tracker = SubagentTracker(
        tool_use_id=tool_id,
        turn_call_id=self.current_turn_call_id,
        detected_at=datetime.now(timezone.utc),
        parent_session_id=self.session_id,
    )
    self._subagent_trackers[tool_id] = tracker
    continue  # Skip normal tool logging - will be handled as subagent
```

### Phase 2: File Scanning

In the existing 500ms poll loop, scan for matching subagent files:

```python
async def _scan_for_subagent_files(self) -> None:
    pending = [t for t in self._subagent_trackers.values() if not t.is_tailing]
    if not pending:
        return

    earliest = min(t.detected_at for t in pending)

    for agent_file in sessions_dir.glob("agent-*.jsonl"):
        # Skip files older than our pending subagents
        if agent_file.stat().st_ctime < earliest.timestamp():
            continue

        # Verify sessionId matches our parent session
        session = parse_session_file(agent_file, limit_lines=10)
        if not session or session.session_id != self.session_id:
            continue

        await self._start_tailing_subagent(session, agent_file)
```

### Phase 3: Start Tailing

When a matching file is found:

1. Update tracker with file info (`agent_id`, `transcript_path`)
2. Add to secondary index (`_subagent_by_agent_id`)
3. Create the `claude_code.subagent` Weave call (eager creation)
4. Process any existing content in the file

### Phase 4: Incremental Processing

Each poll cycle, for all tailing subagents:

1. Re-parse transcript from `last_processed_line`
2. Log new tool calls under the subagent call
3. Update `last_processed_line`

### Phase 5: SubagentStop (Hybrid)

When SubagentStop arrives:

**Fast path** (if tailing):
- Flush remaining content
- Finish the subagent call with aggregated output
- Cleanup trackers

**Fallback path** (if not tailing):
- Full processing (current behavior)
- Create call, log all tools, finish
- Cleanup any orphaned tracker

## Edge Cases

### Timeout for Missing Files

If subagent file doesn't appear within 10 seconds, clean up the tracker:

```python
SUBAGENT_DETECTION_TIMEOUT = 10  # seconds
stale = [t for t in self._subagent_trackers.values()
         if not t.is_tailing
         and (now - t.detected_at).seconds > SUBAGENT_DETECTION_TIMEOUT]
for tracker in stale:
    logger.warning(f"Subagent file not found: {tracker.tool_use_id}")
    del self._subagent_trackers[tracker.tool_use_id]
```

### Daemon Shutdown

Finish any in-progress subagent calls with partial output.

### Multiple Concurrent Subagents

Handled naturally - dict keyed by `tool_use_id`, each tracker independent.

### Fast Subagents

SubagentStop fallback path handles subagents that complete before file detection.

## Files to Modify

| File | Changes |
|------|---------|
| `daemon.py` | Add SubagentTracker dataclass, scanning logic, tailing logic, updated SubagentStop handler |
| `session_parser.py` | May need `start_line` parameter for incremental parsing |

## Files Unchanged

- `hook.py` - Still just relays events to daemon
- `state.py` - Tracker is in-memory only (daemon lifetime)
- `socket_client.py` - No changes needed

## Testing Strategy

1. **Unit tests**: SubagentTracker state transitions
2. **Integration tests**:
   - Subagent file detected and tailed
   - SubagentStop fast path (tailing)
   - SubagentStop fallback path (not tailing)
   - Timeout cleanup
   - Multiple concurrent subagents
3. **Manual testing**: Verify real-time visibility in Weave UI
