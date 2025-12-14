"""Tests for reconstructing file diffs from Edit tool call data.

Claude Code Edit tool results contain:
- originalFile: The complete original file content
- structuredPatch: Unified diff format with line numbers
- oldString/newString: The text that was changed

This allows reconstructing file diffs WITHOUT relying on file-history-snapshot entries,
which are NOT recorded in agent files (only in main session files).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from weave.integrations.claude_plugin.session_parser import (
    ToolCall,
    parse_session_file,
)


# Sample structured patch format from Claude Code
SAMPLE_STRUCTURED_PATCH = [
    {
        "oldStart": 10,
        "oldLines": 4,
        "newStart": 10,
        "newLines": 5,
        "lines": [
            " def hello():",
            "-    pass",
            "+    print('Hello!')",
            "+    return True",
            " ",
            " def main():",
        ],
    }
]

SAMPLE_ORIGINAL_FILE = """# test.py
# A simple test file

def greet(name):
    return f"Hello, {name}!"

def goodbye():
    return "Goodbye!"

def hello():
    pass

def main():
    hello()
    print(greet("World"))
"""


class TestEditToolResultParsing:
    """Test parsing of Edit tool result data for diff reconstruction."""

    def test_parse_edit_tool_result_with_original_file(self, tmp_path):
        """Edit tool results contain originalFile for diff reconstruction."""
        session_file = tmp_path / "test-session.jsonl"

        # Create session with Edit tool call and rich tool_result
        messages = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Edit the file"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/tmp/test.py",
                                "old_string": "def hello():\n    pass",
                                "new_string": "def hello():\n    print('Hello!')",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "File updated successfully",
                        }
                    ],
                },
                # The rich toolUseResult with originalFile
                "toolUseResult": {
                    "filePath": "/tmp/test.py",
                    "oldString": "def hello():\n    pass",
                    "newString": "def hello():\n    print('Hello!')",
                    "originalFile": "# test.py\ndef hello():\n    pass\n\ndef main():\n    hello()\n",
                    "structuredPatch": [
                        {
                            "oldStart": 1,
                            "oldLines": 3,
                            "newStart": 1,
                            "newLines": 3,
                            "lines": [
                                " # test.py",
                                "-def hello():",
                                "-    pass",
                                "+def hello():",
                                "+    print('Hello!')",
                            ],
                        }
                    ],
                },
            },
        ]

        with open(session_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        session = parse_session_file(session_file)
        assert session is not None

        # Verify we have the Edit tool call
        tool_calls = session.turns[0].all_tool_calls()
        assert len(tool_calls) == 1
        tc = tool_calls[0]
        assert tc.name == "Edit"
        assert tc.input["file_path"] == "/tmp/test.py"
        assert "old_string" in tc.input
        assert "new_string" in tc.input


class TestDiffReconstructionFromEditCalls:
    """Test reconstructing diffs from Edit tool call data."""

    def test_extract_file_changes_from_edit_inputs(self):
        """Edit tool inputs contain old_string and new_string for diff."""
        edit_input = {
            "file_path": "/tmp/test.py",
            "old_string": "def foo():\n    return 1",
            "new_string": "def foo():\n    return 2",
        }

        # We can construct a diff from these
        file_path = edit_input["file_path"]
        old_text = edit_input["old_string"]
        new_text = edit_input["new_string"]

        assert file_path == "/tmp/test.py"
        assert old_text != new_text

        # The diff shows what changed
        import difflib
        diff = list(difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=file_path,
            tofile=file_path,
        ))

        assert len(diff) > 0
        diff_text = "".join(diff)
        # Verify the diff contains the change markers
        assert "-    return 1" in diff_text
        assert "+    return 2" in diff_text

    def test_aggregate_multiple_edits_to_same_file(self):
        """Multiple Edit calls to same file can be aggregated."""
        edits = [
            {
                "file_path": "/tmp/test.py",
                "old_string": "foo",
                "new_string": "bar",
            },
            {
                "file_path": "/tmp/test.py",
                "old_string": "baz",
                "new_string": "qux",
            },
            {
                "file_path": "/tmp/other.py",
                "old_string": "x",
                "new_string": "y",
            },
        ]

        # Group edits by file
        edits_by_file: dict[str, list[dict]] = {}
        for edit in edits:
            fp = edit["file_path"]
            if fp not in edits_by_file:
                edits_by_file[fp] = []
            edits_by_file[fp].append(edit)

        assert len(edits_by_file["/tmp/test.py"]) == 2
        assert len(edits_by_file["/tmp/other.py"]) == 1


class TestSubagentEditCollection:
    """Test collecting Edit calls from subagent files."""

    def test_collect_edits_from_subagent_file(self, tmp_path):
        """Can parse Edit tool calls from subagent files."""
        agent_file = tmp_path / "agent-abc123.jsonl"

        messages = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "parent-session",
                "agentId": "abc123",
                "isSidechain": True,
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Edit the file"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "agentId": "abc123",
                "isSidechain": True,
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/tmp/test.py",
                                "old_string": "old",
                                "new_string": "new",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 25},
                },
            },
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "parent-session",
                "agentId": "abc123",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "File updated",
                        }
                    ],
                },
            },
        ]

        with open(agent_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        session = parse_session_file(agent_file)
        assert session is not None

        # Collect Edit calls
        edit_calls = []
        for turn in session.turns:
            for tc in turn.all_tool_calls():
                if tc.name == "Edit":
                    edit_calls.append({
                        "file_path": tc.input.get("file_path"),
                        "old_string": tc.input.get("old_string"),
                        "new_string": tc.input.get("new_string"),
                    })

        assert len(edit_calls) == 1
        assert edit_calls[0]["file_path"] == "/tmp/test.py"


class TestStructuredPatchParsing:
    """Test parsing and using structuredPatch from toolUseResult."""

    def test_parse_structured_patch_from_tool_use_result(self, tmp_path):
        """toolUseResult contains structuredPatch for diff generation."""
        session_file = tmp_path / "test-session.jsonl"

        messages = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Edit the file"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/tmp/test.py",
                                "old_string": "    pass",
                                "new_string": "    print('Hello!')\n    return True",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "File updated successfully",
                        }
                    ],
                },
                "toolUseResult": {
                    "filePath": "/tmp/test.py",
                    "oldString": "    pass",
                    "newString": "    print('Hello!')\n    return True",
                    "originalFile": SAMPLE_ORIGINAL_FILE,
                    "structuredPatch": SAMPLE_STRUCTURED_PATCH,
                    "userModified": False,
                    "replaceAll": False,
                },
            },
        ]

        with open(session_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        session = parse_session_file(session_file)
        assert session is not None

        # Verify Edit tool call exists
        tool_calls = session.turns[0].all_tool_calls()
        assert len(tool_calls) == 1
        tc = tool_calls[0]
        assert tc.name == "Edit"

        # The raw_messages should contain the toolUseResult
        raw_msgs = session.turns[0].raw_messages
        tool_result_msg = next(
            (m for m in raw_msgs if m.get("toolUseResult")), None
        )
        assert tool_result_msg is not None
        assert "originalFile" in tool_result_msg["toolUseResult"]
        assert "structuredPatch" in tool_result_msg["toolUseResult"]

    def test_convert_structured_patch_to_unified_diff(self):
        """Convert structuredPatch to unified diff format."""
        # This functionality is now handled internally by diff_view.py
        # when building file diffs. We can test it via apply_structured_patch.
        from weave.integrations.claude_plugin.diff_utils import (
            apply_structured_patch,
        )
        import difflib

        # Apply patch to get new content
        new_content = apply_structured_patch(
            original_content=SAMPLE_ORIGINAL_FILE,
            structured_patch=SAMPLE_STRUCTURED_PATCH,
        )

        # Generate unified diff from old and new
        diff_lines = list(difflib.unified_diff(
            SAMPLE_ORIGINAL_FILE.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile="a/test.py",
            tofile="b/test.py",
        ))
        diff = "".join(diff_lines)

        # Should be a valid unified diff string
        assert "--- a/test.py" in diff
        assert "+++ b/test.py" in diff
        assert "-    pass" in diff
        assert "+    print('Hello!')" in diff
        assert "+    return True" in diff

    def test_apply_structured_patch_to_original(self):
        """Apply structuredPatch to originalFile to get new content."""
        from weave.integrations.claude_plugin.diff_utils import (
            apply_structured_patch,
        )

        new_content = apply_structured_patch(
            original_content=SAMPLE_ORIGINAL_FILE,
            structured_patch=SAMPLE_STRUCTURED_PATCH,
        )

        # Verify the patch was applied
        assert "print('Hello!')" in new_content
        assert "return True" in new_content
        # Original content should still have the unchanged parts
        assert "def greet(name):" in new_content
        assert "def main():" in new_content

    def test_generate_html_diff_from_structured_patch(self):
        """Generate HTML diff view from structuredPatch data."""
        from weave.integrations.claude_plugin.diff_view import (
            generate_edit_diff_html,
        )

        html = generate_edit_diff_html(
            file_path="/tmp/test.py",
            original_content=SAMPLE_ORIGINAL_FILE,
            structured_patch=SAMPLE_STRUCTURED_PATCH,
        )

        # Should contain HTML diff structure with GitHub-style formatting
        assert "<" in html  # Has HTML tags
        assert "pass" in html  # Contains the removed content
        assert "Hello" in html  # Contains the added content


class TestMultipleEditsToSameFile:
    """Test handling multiple edits to the same file."""

    def test_aggregate_patches_for_same_file(self):
        """Multiple edits to same file should be aggregated."""
        # This functionality is now handled internally by diff_view._build_file_diffs_from_edit_data
        # We can test the aggregation behavior through that function
        from weave.integrations.claude_plugin.diff_view import _build_file_diffs_from_edit_data

        edits = [
            {
                "file_path": "/tmp/test.py",
                "original_file": "line1\nline2\nline3\n",
                "structured_patch": [
                    {"oldStart": 1, "oldLines": 1, "newStart": 1, "newLines": 1,
                     "lines": ["-line1", "+LINE1"]}
                ],
            },
            {
                "file_path": "/tmp/test.py",
                "original_file": "LINE1\nline2\nline3\n",  # After first edit
                "structured_patch": [
                    {"oldStart": 2, "oldLines": 1, "newStart": 2, "newLines": 1,
                     "lines": ["-line2", "+LINE2"]}
                ],
            },
            {
                "file_path": "/tmp/other.py",
                "original_file": "foo\n",
                "structured_patch": [
                    {"oldStart": 1, "oldLines": 1, "newStart": 1, "newLines": 1,
                     "lines": ["-foo", "+bar"]}
                ],
            },
        ]

        file_diffs = _build_file_diffs_from_edit_data(edits)

        # Should have two files
        assert len(file_diffs) == 2
        paths = {fd["path"] for fd in file_diffs}
        assert "/tmp/test.py" in paths
        assert "/tmp/other.py" in paths


class TestEndToEndSubagentDiffGeneration:
    """Test end-to-end HTML diff generation from subagent Edit calls."""

    def test_generate_html_diff_from_subagent_edits(self, tmp_path):
        """Generate HTML diff views from subagent Edit tool results."""
        from weave.integrations.claude_plugin.diff_utils import (
            extract_edit_data_from_raw_messages,
        )
        from weave.integrations.claude_plugin.diff_view import (
            generate_edit_diff_html,
        )

        # Create agent file with Edit call including full toolUseResult
        agent_file = tmp_path / "agent-abc123.jsonl"
        agent_messages = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "parent-session",
                "agentId": "abc123",
                "isSidechain": True,
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Edit the config"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "agentId": "abc123",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "edit-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/tmp/config.py",
                                "old_string": "DEBUG = False",
                                "new_string": "DEBUG = True",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 25},
                },
            },
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "parent-session",
                "agentId": "abc123",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "edit-1",
                            "content": "File updated",
                        }
                    ],
                },
                "toolUseResult": {
                    "filePath": "/tmp/config.py",
                    "oldString": "DEBUG = False",
                    "newString": "DEBUG = True",
                    "originalFile": "# config.py\nAPP_NAME = 'MyApp'\nDEBUG = False\nPORT = 8080\n",
                    "structuredPatch": [
                        {
                            "oldStart": 2,
                            "oldLines": 3,
                            "newStart": 2,
                            "newLines": 3,
                            "lines": [
                                " APP_NAME = 'MyApp'",
                                "-DEBUG = False",
                                "+DEBUG = True",
                                " PORT = 8080",
                            ],
                        }
                    ],
                },
            },
        ]

        with open(agent_file, "w") as f:
            for msg in agent_messages:
                f.write(json.dumps(msg) + "\n")

        # Parse the agent session
        session = parse_session_file(agent_file)
        assert session is not None

        # Extract Edit data from raw messages
        raw_msgs = []
        for turn in session.turns:
            raw_msgs.extend(turn.raw_messages)

        edits = extract_edit_data_from_raw_messages(raw_msgs)
        assert len(edits) == 1

        edit = edits[0]
        assert edit["file_path"] == "/tmp/config.py"
        assert "DEBUG = False" in edit["original_file"]
        assert len(edit["structured_patch"]) == 1

        # Generate HTML diff
        html = generate_edit_diff_html(
            file_path=edit["file_path"],
            original_content=edit["original_file"],
            structured_patch=edit["structured_patch"],
        )

        # Verify HTML contains diff information
        assert "config.py" in html
        assert "DEBUG" in html
        assert "False" in html or "True" in html

    def test_collect_all_subagent_edits_for_session(self, tmp_path):
        """Collect Edit data from multiple subagents in a session."""
        from weave.integrations.claude_plugin.diff_utils import (
            extract_edit_data_from_raw_messages,
        )
        from weave.integrations.claude_plugin.diff_view import _build_file_diffs_from_edit_data

        # Helper to create agent file with edits
        def create_agent_file(agent_id: str, file_path: str, original: str, patch: list):
            agent_file = tmp_path / f"agent-{agent_id}.jsonl"
            messages = [
                {
                    "type": "user",
                    "uuid": f"{agent_id}-u1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "sessionId": "parent",
                    "agentId": agent_id,
                    "isSidechain": True,
                    "cwd": "/tmp",
                    "message": {"role": "user", "content": "Edit"},
                },
                {
                    "type": "assistant",
                    "uuid": f"{agent_id}-a1",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "agentId": agent_id,
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "tool_use", "id": "t1", "name": "Edit", "input": {"file_path": file_path}}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                },
                {
                    "type": "user",
                    "uuid": f"{agent_id}-u2",
                    "timestamp": "2025-01-01T10:00:02Z",
                    "sessionId": "parent",
                    "agentId": agent_id,
                    "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "OK"}]},
                    "toolUseResult": {
                        "filePath": file_path,
                        "originalFile": original,
                        "structuredPatch": patch,
                    },
                },
            ]
            with open(agent_file, "w") as f:
                for msg in messages:
                    f.write(json.dumps(msg) + "\n")
            return agent_file

        # Create two subagents that edit different files
        agent1 = create_agent_file(
            "agent1",
            "/tmp/file1.py",
            "line1\nline2\n",
            [{"oldStart": 1, "oldLines": 1, "newStart": 1, "newLines": 1, "lines": ["-line1", "+LINE1"]}],
        )
        agent2 = create_agent_file(
            "agent2",
            "/tmp/file2.py",
            "foo\nbar\n",
            [{"oldStart": 2, "oldLines": 1, "newStart": 2, "newLines": 1, "lines": ["-bar", "+BAR"]}],
        )

        # Parse both and collect edits
        all_edits = []
        for agent_file in [agent1, agent2]:
            session = parse_session_file(agent_file)
            raw_msgs = []
            for turn in session.turns:
                raw_msgs.extend(turn.raw_messages)
            all_edits.extend(extract_edit_data_from_raw_messages(raw_msgs))

        # Should have 2 edits to 2 different files
        assert len(all_edits) == 2

        file_diffs = _build_file_diffs_from_edit_data(all_edits)
        paths = {fd["path"] for fd in file_diffs}
        assert "/tmp/file1.py" in paths
        assert "/tmp/file2.py" in paths


class TestImporterWithEditDiffs:
    """Test that importer can use Edit tool data for file changes."""

    def test_session_with_subagent_edits_collects_all_changes(self, tmp_path):
        """Importer should collect Edit calls from subagents for file_snapshots."""
        # Create main session with Task call
        session_file = tmp_path / "test-session.jsonl"
        main_messages = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Launch agent"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "general-purpose",
                                "prompt": "Edit files",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:10Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "task-1",
                            "content": "Done.\n\nagentId: abc123",
                        }
                    ],
                },
            },
        ]

        with open(session_file, "w") as f:
            for msg in main_messages:
                f.write(json.dumps(msg) + "\n")

        # Create agent file with Edit calls
        agent_file = tmp_path / "agent-abc123.jsonl"
        agent_messages = [
            {
                "type": "user",
                "uuid": "agent-u1",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "test-session",
                "agentId": "abc123",
                "isSidechain": True,
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Edit files"},
            },
            {
                "type": "assistant",
                "uuid": "agent-a1",
                "timestamp": "2025-01-01T10:00:03Z",
                "agentId": "abc123",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "edit-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/tmp/test.py",
                                "old_string": "def foo(): pass",
                                "new_string": "def foo(): return 42",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 25},
                },
            },
            {
                "type": "user",
                "uuid": "agent-u2",
                "timestamp": "2025-01-01T10:00:04Z",
                "sessionId": "test-session",
                "agentId": "abc123",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "edit-1",
                            "content": "File updated",
                        }
                    ],
                },
            },
        ]

        with open(agent_file, "w") as f:
            for msg in agent_messages:
                f.write(json.dumps(msg) + "\n")

        # Parse both sessions
        main_session = parse_session_file(session_file)
        agent_session = parse_session_file(agent_file)

        # Collect all edited files from main session and subagent
        all_edited_files = set()

        # From main session
        for turn in main_session.turns:
            for tc in turn.all_tool_calls():
                if tc.name in ("Edit", "Write"):
                    fp = tc.input.get("file_path")
                    if fp:
                        all_edited_files.add(fp)

        # From subagent
        for turn in agent_session.turns:
            for tc in turn.all_tool_calls():
                if tc.name in ("Edit", "Write"):
                    fp = tc.input.get("file_path")
                    if fp:
                        all_edited_files.add(fp)

        # Verify we found the subagent's edit
        assert "/tmp/test.py" in all_edited_files
