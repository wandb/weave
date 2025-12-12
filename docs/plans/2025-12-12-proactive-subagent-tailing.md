# Proactive Subagent File Tailing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable real-time visibility of subagent tool calls in Weave by detecting and tailing subagent files as they're created, rather than waiting for SubagentStop.

**Architecture:** When a Task tool with `subagent_type` is detected in the parent transcript, record the detection timestamp. Scan for new `agent-*.jsonl` files in the sessions directory, match by `sessionId` to our parent session, then tail the file and create Weave traces incrementally. SubagentStop finishes the trace (fast path) or falls back to current behavior.

**Tech Stack:** Python asyncio, existing session_parser.py, Weave tracing

---

## Task 1: Add SubagentTracker Dataclass

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py:82-110`
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
# tests/integrations/claude_plugin/test_daemon.py
from datetime import datetime, timezone

def test_subagent_tracker_is_tailing_false_when_no_call_id():
    """SubagentTracker.is_tailing returns False until subagent_call_id is set."""
    from weave.integrations.claude_plugin.daemon import SubagentTracker

    tracker = SubagentTracker(
        tool_use_id="tool-123",
        turn_call_id="turn-456",
        detected_at=datetime.now(timezone.utc),
        parent_session_id="session-789",
    )

    assert tracker.is_tailing is False
    assert tracker.agent_id is None
    assert tracker.transcript_path is None


def test_subagent_tracker_is_tailing_true_when_call_id_set():
    """SubagentTracker.is_tailing returns True once subagent_call_id is set."""
    from weave.integrations.claude_plugin.daemon import SubagentTracker
    from pathlib import Path

    tracker = SubagentTracker(
        tool_use_id="tool-123",
        turn_call_id="turn-456",
        detected_at=datetime.now(timezone.utc),
        parent_session_id="session-789",
    )

    # Simulate finding the file
    tracker.agent_id = "abc12345"
    tracker.transcript_path = Path("/tmp/agent-abc12345.jsonl")
    tracker.subagent_call_id = "weave-call-xyz"

    assert tracker.is_tailing is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_subagent_tracker_is_tailing_false_when_no_call_id -v`
Expected: FAIL with "cannot import name 'SubagentTracker'"

**Step 3: Write minimal implementation**

Add to `daemon.py` after the imports (around line 77, before `INACTIVITY_TIMEOUT`):

```python
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class SubagentTracker:
    """Tracks a subagent through its lifecycle: pending -> tailing -> finished."""

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

**Step 4: Run tests to verify they pass**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_subagent_tracker_is_tailing_false_when_no_call_id tests/integrations/claude_plugin/test_daemon.py::test_subagent_tracker_is_tailing_true_when_call_id_set -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add SubagentTracker dataclass for lifecycle tracking"
```

---

## Task 2: Add Tracker Dictionaries to WeaveDaemon

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py:85-110` (WeaveDaemon.__init__)
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
def test_daemon_has_subagent_tracker_dicts():
    """WeaveDaemon has dictionaries for tracking subagents."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon

    daemon = WeaveDaemon("test-session-123")

    assert hasattr(daemon, '_subagent_trackers')
    assert hasattr(daemon, '_subagent_by_agent_id')
    assert isinstance(daemon._subagent_trackers, dict)
    assert isinstance(daemon._subagent_by_agent_id, dict)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_daemon_has_subagent_tracker_dicts -v`
Expected: FAIL with "AssertionError" (missing attributes)

**Step 3: Write minimal implementation**

In `WeaveDaemon.__init__` (around line 109), replace the existing `_pending_subagent_tasks` line with:

```python
        # Track pending subagent Task tool calls: tool_use_id -> turn_call_id
        self._pending_subagent_tasks: dict[str, str] = {}  # Keep for backwards compat

        # NEW: Full lifecycle tracking for proactive subagent tailing
        # Primary index: tool_use_id (known at detection)
        self._subagent_trackers: dict[str, SubagentTracker] = {}
        # Secondary index: agent_id (known once file found, for SubagentStop lookup)
        self._subagent_by_agent_id: dict[str, SubagentTracker] = {}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_daemon_has_subagent_tracker_dicts -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add subagent tracker dictionaries to WeaveDaemon"
```

---

## Task 3: Update Detection Logic to Create Tracker

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py:775-781` (_handle_assistant_message)
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_task_tool_with_subagent_type_creates_tracker():
    """Task tool with subagent_type creates SubagentTracker."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker

    daemon = WeaveDaemon("test-session-123")
    daemon.weave_client = MagicMock()
    daemon.current_turn_call_id = "turn-call-456"
    daemon.session_call_id = "session-call-789"
    daemon.trace_id = "trace-abc"

    # Simulate assistant message with Task tool containing subagent_type
    obj = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool-use-xyz",
                    "name": "Task",
                    "input": {
                        "prompt": "Search the codebase",
                        "subagent_type": "Explore",
                    }
                }
            ]
        }
    }

    await daemon._handle_assistant_message(obj, line_num=10)

    # Verify tracker was created
    assert "tool-use-xyz" in daemon._subagent_trackers
    tracker = daemon._subagent_trackers["tool-use-xyz"]
    assert isinstance(tracker, SubagentTracker)
    assert tracker.tool_use_id == "tool-use-xyz"
    assert tracker.turn_call_id == "turn-call-456"
    assert tracker.parent_session_id == "test-session-123"
    assert tracker.is_tailing is False  # Not yet found file
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_task_tool_with_subagent_type_creates_tracker -v`
Expected: FAIL with "KeyError" (tracker not created)

**Step 3: Write minimal implementation**

In `_handle_assistant_message` (around line 777-781), update the Task tool handling:

```python
                # Skip Task tools with subagent_type - they'll be handled by SubagentStop
                # This prevents duplicate logging (once as tool, once as subagent)
                if tool_name == "Task" and tool_input.get("subagent_type"):
                    # Track this for SubagentStop to know which turn to attach to
                    self._pending_subagent_tasks[tool_id] = self.current_turn_call_id

                    # NEW: Create full lifecycle tracker for proactive tailing
                    tracker = SubagentTracker(
                        tool_use_id=tool_id,
                        turn_call_id=self.current_turn_call_id,
                        detected_at=datetime.now(timezone.utc),
                        parent_session_id=self.session_id,
                    )
                    self._subagent_trackers[tool_id] = tracker

                    logger.debug(f"Subagent detected: tool_id={tool_id}, will scan for file")
                    continue
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_task_tool_with_subagent_type_creates_tracker -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Create SubagentTracker when Task tool with subagent_type detected"
```

---

## Task 4: Add Sessions Directory Helper

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py`
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
def test_daemon_get_sessions_directory():
    """WeaveDaemon can determine the sessions directory from transcript path."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon
    from pathlib import Path

    daemon = WeaveDaemon("test-session-123")
    daemon.transcript_path = Path("/Users/test/.claude/projects/abc123/session-xyz.jsonl")

    sessions_dir = daemon._get_sessions_directory()

    assert sessions_dir == Path("/Users/test/.claude/projects/abc123")


def test_daemon_get_sessions_directory_none_when_no_transcript():
    """WeaveDaemon returns None when no transcript path set."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon

    daemon = WeaveDaemon("test-session-123")
    daemon.transcript_path = None

    sessions_dir = daemon._get_sessions_directory()

    assert sessions_dir is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_daemon_get_sessions_directory -v`
Expected: FAIL with "AttributeError" (method doesn't exist)

**Step 3: Write minimal implementation**

Add method to `WeaveDaemon` class (after `_save_state`, around line 193):

```python
    def _get_sessions_directory(self) -> Path | None:
        """Get the sessions directory containing transcript files."""
        if not self.transcript_path:
            return None
        return self.transcript_path.parent
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_daemon_get_sessions_directory tests/integrations/claude_plugin/test_daemon.py::test_daemon_get_sessions_directory_none_when_no_transcript -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add sessions directory helper method"
```

---

## Task 5: Add Subagent File Scanning Method

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py`
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
import tempfile
import json
from pathlib import Path

@pytest.mark.asyncio
async def test_scan_for_subagent_files_finds_matching_file(tmp_path):
    """_scan_for_subagent_files finds and matches subagent files by sessionId."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker
    from datetime import datetime, timezone
    import time

    daemon = WeaveDaemon("parent-session-uuid")
    daemon.session_id = "parent-session-uuid"
    daemon.transcript_path = tmp_path / "session.jsonl"
    daemon.transcript_path.touch()

    # Create a pending tracker
    tracker = SubagentTracker(
        tool_use_id="tool-123",
        turn_call_id="turn-456",
        detected_at=datetime.now(timezone.utc),
        parent_session_id="parent-session-uuid",
    )
    daemon._subagent_trackers["tool-123"] = tracker

    # Wait a tiny bit so file will be "after" detection
    time.sleep(0.01)

    # Create a subagent file with matching sessionId
    agent_file = tmp_path / "agent-abc123.jsonl"
    agent_file.write_text(json.dumps({
        "type": "assistant",
        "sessionId": "parent-session-uuid",
        "agentId": "abc123",
        "isSidechain": True,
        "message": {"content": [{"type": "text", "text": "Hello"}]}
    }) + "\n")

    # Mock _start_tailing_subagent to track if it gets called
    start_tailing_called = []
    async def mock_start_tailing(session, path):
        start_tailing_called.append((session.agent_id, path))
    daemon._start_tailing_subagent = mock_start_tailing

    await daemon._scan_for_subagent_files()

    assert len(start_tailing_called) == 1
    assert start_tailing_called[0][0] == "abc123"


@pytest.mark.asyncio
async def test_scan_for_subagent_files_ignores_other_sessions(tmp_path):
    """_scan_for_subagent_files ignores files from other sessions."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker
    from datetime import datetime, timezone

    daemon = WeaveDaemon("parent-session-uuid")
    daemon.session_id = "parent-session-uuid"
    daemon.transcript_path = tmp_path / "session.jsonl"
    daemon.transcript_path.touch()

    # Create a pending tracker
    tracker = SubagentTracker(
        tool_use_id="tool-123",
        turn_call_id="turn-456",
        detected_at=datetime.now(timezone.utc),
        parent_session_id="parent-session-uuid",
    )
    daemon._subagent_trackers["tool-123"] = tracker

    # Create a subagent file with DIFFERENT sessionId
    agent_file = tmp_path / "agent-other.jsonl"
    agent_file.write_text(json.dumps({
        "type": "assistant",
        "sessionId": "different-session-uuid",
        "agentId": "other",
        "isSidechain": True,
        "message": {"content": [{"type": "text", "text": "Hello"}]}
    }) + "\n")

    start_tailing_called = []
    async def mock_start_tailing(session, path):
        start_tailing_called.append((session.agent_id, path))
    daemon._start_tailing_subagent = mock_start_tailing

    await daemon._scan_for_subagent_files()

    # Should NOT have started tailing - wrong session
    assert len(start_tailing_called) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_scan_for_subagent_files_finds_matching_file -v`
Expected: FAIL with "AttributeError" (method doesn't exist)

**Step 3: Write minimal implementation**

Add method to `WeaveDaemon` class (after `_get_sessions_directory`):

```python
    async def _scan_for_subagent_files(self) -> None:
        """Scan for agent-*.jsonl files matching pending subagents."""
        # Get pending (non-tailing) trackers
        pending = [t for t in self._subagent_trackers.values() if not t.is_tailing]
        if not pending:
            return

        sessions_dir = self._get_sessions_directory()
        if not sessions_dir or not sessions_dir.exists():
            return

        # Get earliest detection time for filtering
        earliest = min(t.detected_at for t in pending)

        for agent_file in sessions_dir.glob("agent-*.jsonl"):
            try:
                # Skip files created before any pending subagent
                file_ctime = agent_file.stat().st_ctime
                if file_ctime < earliest.timestamp():
                    continue

                # Parse first few lines to check sessionId
                session = parse_session_file(agent_file)
                if not session:
                    continue

                # Verify sessionId matches our parent session
                if session.session_id != self.session_id:
                    continue

                # Match! Start tailing
                await self._start_tailing_subagent(session, agent_file)

            except Exception as e:
                logger.debug(f"Error checking agent file {agent_file}: {e}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_scan_for_subagent_files_finds_matching_file tests/integrations/claude_plugin/test_daemon.py::test_scan_for_subagent_files_ignores_other_sessions -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add subagent file scanning method"
```

---

## Task 6: Add Start Tailing Method

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py`
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_start_tailing_subagent_creates_weave_call(tmp_path):
    """_start_tailing_subagent creates Weave call and updates tracker."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker
    from weave.integrations.claude_plugin.session_parser import Session
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    daemon = WeaveDaemon("parent-session-uuid")
    daemon.session_id = "parent-session-uuid"
    daemon.weave_client = MagicMock()
    daemon.weave_client._project_id.return_value = "test-project"
    daemon.trace_id = "trace-123"
    daemon.session_call_id = "session-call-456"
    daemon.current_turn_call_id = "turn-call-789"

    # Mock create_call to return a call with an id
    mock_call = MagicMock()
    mock_call.id = "subagent-call-xyz"
    daemon.weave_client.create_call.return_value = mock_call

    # Create a pending tracker
    tracker = SubagentTracker(
        tool_use_id="tool-123",
        turn_call_id="turn-call-789",
        detected_at=datetime.now(timezone.utc),
        parent_session_id="parent-session-uuid",
    )
    daemon._subagent_trackers["tool-123"] = tracker

    # Create mock session
    session = MagicMock(spec=Session)
    session.session_id = "parent-session-uuid"
    session.agent_id = "abc123"
    session.turns = []
    session.first_user_prompt.return_value = "Search the codebase"

    agent_file = tmp_path / "agent-abc123.jsonl"
    agent_file.touch()

    await daemon._start_tailing_subagent(session, agent_file)

    # Verify tracker was updated
    assert tracker.agent_id == "abc123"
    assert tracker.transcript_path == agent_file
    assert tracker.subagent_call_id == "subagent-call-xyz"
    assert tracker.is_tailing is True

    # Verify secondary index was populated
    assert daemon._subagent_by_agent_id["abc123"] is tracker

    # Verify Weave call was created
    daemon.weave_client.create_call.assert_called_once()
    call_kwargs = daemon.weave_client.create_call.call_args.kwargs
    assert call_kwargs["op"] == "claude_code.subagent"
    assert "abc123" in call_kwargs["inputs"]["agent_id"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_start_tailing_subagent_creates_weave_call -v`
Expected: FAIL with "AttributeError" (method doesn't exist)

**Step 3: Write minimal implementation**

Add method to `WeaveDaemon` class (after `_scan_for_subagent_files`):

```python
    async def _start_tailing_subagent(self, session: Session, agent_file: Path) -> None:
        """Create subagent call and start tailing the file."""
        if not self.weave_client:
            return

        # Find the tracker (match by parent session)
        tracker = next(
            (t for t in self._subagent_trackers.values()
             if not t.is_tailing and t.parent_session_id == session.session_id),
            None
        )
        if not tracker:
            logger.debug(f"No pending tracker for subagent file {agent_file}")
            return

        # Update tracker with file info
        tracker.agent_id = session.agent_id
        tracker.transcript_path = agent_file
        self._subagent_by_agent_id[session.agent_id] = tracker

        # Build display name
        first_prompt = session.first_user_prompt() or ""
        if first_prompt:
            display_name = f"SubAgent: {truncate(first_prompt, 50)}"
        else:
            display_name = f"SubAgent: {session.agent_id}"

        # Determine parent: prefer current turn, fall back to session
        from weave.trace.call import Call
        parent_id = tracker.turn_call_id or self.session_call_id
        parent_call = Call(
            _op_name="",
            project_id=self.weave_client._project_id(),
            trace_id=self.trace_id,
            parent_id=self.session_call_id if tracker.turn_call_id else None,
            inputs={},
            id=parent_id,
        )

        # Create subagent call (eager creation)
        subagent_call = self.weave_client.create_call(
            op="claude_code.subagent",
            inputs={
                "agent_id": session.agent_id,
                "prompt": truncate(first_prompt, 2000),
            },
            parent=parent_call,
            display_name=display_name,
            attributes={"agent_id": session.agent_id, "is_sidechain": True},
            use_stack=False,
        )

        tracker.subagent_call_id = subagent_call.id

        logger.info(f"Started tailing subagent {session.agent_id}: {subagent_call.id}")

        # Process any existing content
        await self._process_subagent_updates(tracker)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_start_tailing_subagent_creates_weave_call -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add start tailing method for subagents"
```

---

## Task 7: Add Incremental Subagent Processing Method

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py`
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_process_subagent_updates_logs_tool_calls(tmp_path):
    """_process_subagent_updates logs new tool calls."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch
    import json

    daemon = WeaveDaemon("parent-session-uuid")
    daemon.weave_client = MagicMock()
    daemon.weave_client._project_id.return_value = "test-project"
    daemon.trace_id = "trace-123"

    # Create agent file with tool calls
    agent_file = tmp_path / "agent-abc123.jsonl"
    agent_file.write_text(
        json.dumps({
            "type": "assistant",
            "sessionId": "parent-session-uuid",
            "agentId": "abc123",
            "isSidechain": True,
            "uuid": "msg-1",
            "timestamp": "2025-01-01T10:00:00Z",
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-20250514",
                "content": [
                    {"type": "text", "text": "Searching..."},
                    {"type": "tool_use", "id": "tool-1", "name": "Grep", "input": {"pattern": "TODO"}},
                ],
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }
        }) + "\n"
    )

    # Create tracker in tailing state
    tracker = SubagentTracker(
        tool_use_id="tool-123",
        turn_call_id="turn-456",
        detected_at=datetime.now(timezone.utc),
        parent_session_id="parent-session-uuid",
        agent_id="abc123",
        transcript_path=agent_file,
        subagent_call_id="subagent-call-xyz",
        last_processed_line=0,
    )

    with patch("weave.integrations.claude_plugin.daemon.weave") as mock_weave:
        await daemon._process_subagent_updates(tracker)

    # Verify tool call was logged
    mock_weave.log_call.assert_called()
    call_kwargs = mock_weave.log_call.call_args.kwargs
    assert "Grep" in call_kwargs["op"]

    # Verify last_processed_line was updated
    assert tracker.last_processed_line > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_process_subagent_updates_logs_tool_calls -v`
Expected: FAIL with "AttributeError" (method doesn't exist)

**Step 3: Write minimal implementation**

Add method to `WeaveDaemon` class (after `_start_tailing_subagent`):

```python
    async def _process_subagent_updates(self, tracker: SubagentTracker) -> None:
        """Process new lines in subagent transcript file."""
        if not tracker.transcript_path or not tracker.subagent_call_id:
            return

        if not tracker.transcript_path.exists():
            return

        # Count lines in file
        with open(tracker.transcript_path) as f:
            lines = f.readlines()
        total_lines = len(lines)

        # Skip if no new lines
        if total_lines <= tracker.last_processed_line:
            return

        # Re-parse the full file to get session data
        # (Could be optimized to parse incrementally, but this is simpler)
        session = parse_session_file(tracker.transcript_path)
        if not session:
            return

        # Reconstruct subagent call as parent
        from weave.trace.call import Call
        subagent_call = Call(
            _op_name="",
            project_id=self.weave_client._project_id(),
            trace_id=self.trace_id,
            parent_id=tracker.turn_call_id,
            inputs={},
            id=tracker.subagent_call_id,
        )

        # Log tool calls from all turns
        # For simple subagents (single turn), log flat under subagent
        for turn in session.turns:
            for tool_call in turn.all_tool_calls():
                tool_name = tool_call.name

                # Sanitize input
                sanitized_input = {}
                for k, v in tool_call.input.items():
                    if isinstance(v, str) and len(v) > 5000:
                        sanitized_input[k] = truncate(v)
                    else:
                        sanitized_input[k] = v

                tool_display = get_tool_display_name(tool_name, tool_call.input)

                weave.log_call(
                    op=f"claude_code.tool.{tool_name}",
                    inputs=sanitized_input,
                    output={"result": truncate(str(tool_call.result), 5000)} if tool_call.result else None,
                    attributes={"tool_name": tool_name},
                    display_name=tool_display,
                    parent=subagent_call,
                    use_stack=False,
                )

        tracker.last_processed_line = total_lines
        logger.debug(f"Processed subagent {tracker.agent_id} up to line {total_lines}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_process_subagent_updates_logs_tool_calls -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add incremental subagent processing method"
```

---

## Task 8: Integrate Scanning into Poll Loop

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py:609-624` (_run_file_tailer)

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_file_tailer_calls_scan_for_subagent_files():
    """File tailer loop calls _scan_for_subagent_files."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon
    from unittest.mock import MagicMock, AsyncMock, patch
    from pathlib import Path
    import asyncio

    daemon = WeaveDaemon("test-session")
    daemon.transcript_path = Path("/tmp/test.jsonl")
    daemon.running = True

    scan_calls = []
    process_calls = []

    async def mock_scan():
        scan_calls.append(1)
        # Stop after first iteration
        daemon.running = False

    async def mock_process():
        process_calls.append(1)

    daemon._scan_for_subagent_files = mock_scan
    daemon._process_session_file = mock_process

    await daemon._run_file_tailer()

    assert len(scan_calls) == 1
    assert len(process_calls) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_file_tailer_calls_scan_for_subagent_files -v`
Expected: FAIL (scan not called)

**Step 3: Write minimal implementation**

Update `_run_file_tailer` method (around line 617-623):

```python
    async def _run_file_tailer(self) -> None:
        """Tail the session file for new content."""
        if not self.transcript_path:
            logger.warning("No transcript path, file tailer not starting")
            return

        logger.debug(f"Starting file tailer for {self.transcript_path}")

        while self.running:
            try:
                # Process parent session transcript
                await self._process_session_file()

                # Scan for subagent files (only if pending trackers)
                await self._scan_for_subagent_files()

                # Process updates for all tailing subagents
                for tracker in list(self._subagent_trackers.values()):
                    if tracker.is_tailing:
                        await self._process_subagent_updates(tracker)

            except Exception as e:
                logger.error(f"Error processing session file: {e}")

            await asyncio.sleep(0.5)  # Poll every 500ms
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_file_tailer_calls_scan_for_subagent_files -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Integrate subagent scanning into poll loop"
```

---

## Task 9: Update SubagentStop for Fast Path

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py:370-565` (_handle_subagent_stop)
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_subagent_stop_fast_path_when_tailing(tmp_path):
    """SubagentStop uses fast path when already tailing."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, AsyncMock
    import json

    daemon = WeaveDaemon("parent-session-uuid")
    daemon.weave_client = MagicMock()
    daemon.weave_client._project_id.return_value = "test-project"
    daemon.trace_id = "trace-123"
    daemon.session_call_id = "session-call-456"

    # Create agent file
    agent_file = tmp_path / "agent-abc123.jsonl"
    agent_file.write_text(json.dumps({
        "type": "assistant",
        "sessionId": "parent-session-uuid",
        "agentId": "abc123",
        "isSidechain": True,
        "uuid": "msg-1",
        "timestamp": "2025-01-01T10:00:00Z",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Done!"}],
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }
    }) + "\n")

    # Create tracker in tailing state
    tracker = SubagentTracker(
        tool_use_id="tool-123",
        turn_call_id="turn-456",
        detected_at=datetime.now(timezone.utc),
        parent_session_id="parent-session-uuid",
        agent_id="abc123",
        transcript_path=agent_file,
        subagent_call_id="subagent-call-xyz",
        last_processed_line=1,
    )
    daemon._subagent_trackers["tool-123"] = tracker
    daemon._subagent_by_agent_id["abc123"] = tracker

    # Mock process_subagent_updates
    daemon._process_subagent_updates = AsyncMock()

    payload = {
        "agent_transcript_path": str(agent_file),
        "agent_id": "abc123",
    }

    result = await daemon._handle_subagent_stop(payload)

    # Verify fast path was used
    assert result["status"] == "ok"
    daemon._process_subagent_updates.assert_called_once_with(tracker)
    daemon.weave_client.finish_call.assert_called_once()

    # Verify cleanup
    assert "tool-123" not in daemon._subagent_trackers
    assert "abc123" not in daemon._subagent_by_agent_id
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_subagent_stop_fast_path_when_tailing -v`
Expected: FAIL (fast path not implemented)

**Step 3: Write minimal implementation**

Update `_handle_subagent_stop` to check for tailing state first (add at the beginning, around line 380):

```python
    async def _handle_subagent_stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle SubagentStop - finish existing call or fall back to full processing.

        Uses fast path if we're already tailing the subagent, otherwise falls back
        to the original behavior of processing the entire file at once.
        """
        agent_id_from_payload = payload.get("agent_id")
        transcript_path = payload.get("agent_transcript_path")

        logger.info(f"SubagentStop: agent_id={agent_id_from_payload}, transcript={transcript_path}")

        # Check if we're already tailing this subagent (FAST PATH)
        tracker = self._subagent_by_agent_id.get(agent_id_from_payload)

        if tracker and tracker.is_tailing:
            logger.info(f"SubagentStop: fast path for tailed subagent {agent_id_from_payload}")

            # Process any remaining content
            await self._process_subagent_updates(tracker)

            # Finish the subagent call
            from weave.trace.call import Call
            subagent_call = Call(
                _op_name="",
                project_id=self.weave_client._project_id(),
                trace_id=self.trace_id,
                parent_id=tracker.turn_call_id,
                inputs={},
                id=tracker.subagent_call_id,
            )

            # Parse file for final output
            session = parse_session_file(tracker.transcript_path)
            final_output = None
            total_usage = None
            tool_counts: dict[str, int] = {}

            if session:
                # Get final response
                if session.turns:
                    last_turn = session.turns[-1]
                    if last_turn.assistant_messages:
                        final_output = last_turn.assistant_messages[-1].get_text()

                # Aggregate usage and tool counts
                total_usage = session.total_usage()
                for turn in session.turns:
                    for tc in turn.all_tool_calls():
                        tool_counts[tc.name] = tool_counts.get(tc.name, 0) + 1

            self.weave_client.finish_call(
                subagent_call,
                output={
                    "response": truncate(final_output, 10000) if final_output else None,
                    "turn_count": len(session.turns) if session else 0,
                    "tool_call_count": sum(tool_counts.values()),
                    "tool_counts": tool_counts,
                    "usage": total_usage.to_weave_usage() if total_usage else None,
                },
            )
            self.weave_client.flush()

            # Cleanup trackers
            if tracker.tool_use_id in self._subagent_trackers:
                del self._subagent_trackers[tracker.tool_use_id]
            if agent_id_from_payload in self._subagent_by_agent_id:
                del self._subagent_by_agent_id[agent_id_from_payload]

            logger.info(f"SubagentStop: finished tailed subagent {agent_id_from_payload}")
            return {"status": "ok"}

        # FALLBACK PATH: Not tailing, use original behavior
        logger.info(f"SubagentStop: fallback path for {agent_id_from_payload} (not tailed)")

        # Clean up any orphaned tracker
        if tracker and tracker.tool_use_id in self._subagent_trackers:
            del self._subagent_trackers[tracker.tool_use_id]

        # ... rest of original implementation continues below ...
```

Note: Keep all the original `_handle_subagent_stop` code below this new section, starting from the original line 380 (`transcript_path = payload.get("agent_transcript_path")`), but rename it to be the fallback path.

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_subagent_stop_fast_path_when_tailing -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add fast path to SubagentStop when already tailing"
```

---

## Task 10: Add Timeout Cleanup for Stale Trackers

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py`
- Test: `tests/integrations/claude_plugin/test_daemon.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_cleanup_stale_subagent_trackers():
    """Stale subagent trackers are cleaned up after timeout."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker, SUBAGENT_DETECTION_TIMEOUT
    from datetime import datetime, timezone, timedelta

    daemon = WeaveDaemon("test-session")

    # Create a stale tracker (detected 15 seconds ago, beyond 10s timeout)
    stale_tracker = SubagentTracker(
        tool_use_id="stale-tool",
        turn_call_id="turn-456",
        detected_at=datetime.now(timezone.utc) - timedelta(seconds=15),
        parent_session_id="test-session",
    )
    daemon._subagent_trackers["stale-tool"] = stale_tracker

    # Create a fresh tracker (detected 2 seconds ago)
    fresh_tracker = SubagentTracker(
        tool_use_id="fresh-tool",
        turn_call_id="turn-789",
        detected_at=datetime.now(timezone.utc) - timedelta(seconds=2),
        parent_session_id="test-session",
    )
    daemon._subagent_trackers["fresh-tool"] = fresh_tracker

    daemon._cleanup_stale_subagent_trackers()

    # Stale tracker should be removed
    assert "stale-tool" not in daemon._subagent_trackers
    # Fresh tracker should remain
    assert "fresh-tool" in daemon._subagent_trackers
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_cleanup_stale_subagent_trackers -v`
Expected: FAIL (method doesn't exist, constant doesn't exist)

**Step 3: Write minimal implementation**

Add constant after `INACTIVITY_TIMEOUT` (around line 79):

```python
# Timeout for subagent file detection (10 seconds)
SUBAGENT_DETECTION_TIMEOUT = 10
```

Add method to `WeaveDaemon` class (after `_process_subagent_updates`):

```python
    def _cleanup_stale_subagent_trackers(self) -> None:
        """Clean up trackers for subagents whose files never appeared."""
        now = datetime.now(timezone.utc)
        stale_tool_ids = [
            tracker.tool_use_id
            for tracker in self._subagent_trackers.values()
            if not tracker.is_tailing
            and (now - tracker.detected_at).total_seconds() > SUBAGENT_DETECTION_TIMEOUT
        ]

        for tool_id in stale_tool_ids:
            tracker = self._subagent_trackers.pop(tool_id, None)
            if tracker:
                logger.warning(
                    f"Subagent file not found after {SUBAGENT_DETECTION_TIMEOUT}s: "
                    f"tool_id={tool_id}"
                )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_cleanup_stale_subagent_trackers -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Add timeout cleanup for stale subagent trackers"
```

---

## Task 11: Integrate Cleanup into Poll Loop

**Files:**
- Modify: `weave/integrations/claude_plugin/daemon.py` (_run_file_tailer)

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_file_tailer_calls_cleanup():
    """File tailer loop calls _cleanup_stale_subagent_trackers."""
    from weave.integrations.claude_plugin.daemon import WeaveDaemon
    from pathlib import Path

    daemon = WeaveDaemon("test-session")
    daemon.transcript_path = Path("/tmp/test.jsonl")
    daemon.running = True

    cleanup_calls = []

    def mock_cleanup():
        cleanup_calls.append(1)
        daemon.running = False  # Stop after first iteration

    async def noop():
        pass

    daemon._cleanup_stale_subagent_trackers = mock_cleanup
    daemon._process_session_file = noop
    daemon._scan_for_subagent_files = noop

    await daemon._run_file_tailer()

    assert len(cleanup_calls) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_file_tailer_calls_cleanup -v`
Expected: FAIL (cleanup not called)

**Step 3: Write minimal implementation**

Update `_run_file_tailer` to add cleanup call (after subagent processing):

```python
                # Clean up stale trackers (file never appeared)
                self._cleanup_stale_subagent_trackers()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integrations/claude_plugin/test_daemon.py::test_file_tailer_calls_cleanup -v`
Expected: PASS

**Step 5: Commit**

```bash
git add weave/integrations/claude_plugin/daemon.py tests/integrations/claude_plugin/test_daemon.py
git commit -m "feat(claude-plugin): Integrate stale tracker cleanup into poll loop"
```

---

## Task 12: Run Full Test Suite and Manual Verification

**Files:**
- All modified files

**Step 1: Run full test suite**

Run: `pytest tests/integrations/claude_plugin/ -v`
Expected: All tests PASS

**Step 2: Run with existing daemon tests**

Run: `pytest tests/integrations/claude_plugin/test_daemon_integration.py -v`
Expected: All tests PASS

**Step 3: Manual verification (if possible)**

1. Start a Claude Code session with `DEBUG=1`
2. Trigger a subagent (use Task tool)
3. Check daemon logs at `/tmp/weave-claude-daemon.log`:
   - Should see "Subagent detected: tool_id=..."
   - Should see "Started tailing subagent..."
   - Should see "SubagentStop: fast path for tailed subagent..."
4. Check Weave UI - tool calls should appear in real-time

**Step 4: Commit**

```bash
git add -A
git commit -m "test(claude-plugin): Verify proactive subagent tailing implementation"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add SubagentTracker dataclass |
| 2 | Add tracker dictionaries to WeaveDaemon |
| 3 | Update detection to create tracker |
| 4 | Add sessions directory helper |
| 5 | Add subagent file scanning |
| 6 | Add start tailing method |
| 7 | Add incremental processing |
| 8 | Integrate scanning into poll loop |
| 9 | Update SubagentStop for fast path |
| 10 | Add timeout cleanup |
| 11 | Integrate cleanup into poll loop |
| 12 | Run full test suite |

**Total: 12 tasks, ~45-60 minutes estimated**
