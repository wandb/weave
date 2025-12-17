"""Tests for Claude Code session parser."""

import json
import tempfile
from pathlib import Path

import pytest

from weave.integrations.claude_plugin.session.session_parser import (
    UserMessage,
    parse_session_file,
)
from weave.type_wrappers.Content.content import Content


# Small 1x1 red PNG image as base64
TINY_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


def create_session_jsonl(messages: list[dict]) -> Path:
    """Create a temporary JSONL session file from message dicts."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for msg in messages:
        tmp.write(json.dumps(msg) + "\n")
    tmp.close()
    return Path(tmp.name)


class TestThinkingContent:
    """Tests for parsing thinking content from assistant messages."""

    def test_assistant_message_with_thinking_extracts_content(self):
        """Assistant messages with thinking blocks should have thinking content extracted."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "What is 2 + 2?",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "The user is asking for a simple arithmetic calculation. 2 + 2 = 4.",
                            "signature": "abc123signature",
                        },
                        {"type": "text", "text": "2 + 2 = 4"},
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            assert session is not None
            assert len(session.turns) == 1

            turn = session.turns[0]
            assert len(turn.assistant_messages) == 1

            assistant_msg = turn.assistant_messages[0]

            # Text content should still be extracted
            assert assistant_msg.get_text() == "2 + 2 = 4"

            # Thinking content should be extracted
            assert hasattr(assistant_msg, "thinking_content"), "AssistantMessage should have 'thinking_content' attribute"
            assert assistant_msg.thinking_content == "The user is asking for a simple arithmetic calculation. 2 + 2 = 4."
        finally:
            session_jsonl.unlink()

    def test_assistant_message_without_thinking_has_none(self):
        """Assistant messages without thinking blocks should have None thinking content."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "Hello",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi there!"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            assert session is not None
            turn = session.turns[0]
            assistant_msg = turn.assistant_messages[0]

            assert hasattr(assistant_msg, "thinking_content")
            assert assistant_msg.thinking_content is None
        finally:
            session_jsonl.unlink()

    def test_multiple_assistant_messages_with_thinking(self):
        """Multiple assistant messages in a turn can each have thinking content."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "Help me with this task",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "First thinking block",
                            "signature": "sig1",
                        },
                        {"type": "text", "text": "First response"},
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 5},
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-3",
                "timestamp": "2025-01-01T10:00:02Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "Second thinking block",
                            "signature": "sig2",
                        },
                        {"type": "text", "text": "Second response"},
                    ],
                    "usage": {"input_tokens": 60, "output_tokens": 6},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            assert session is not None
            turn = session.turns[0]
            assert len(turn.assistant_messages) == 2

            assert turn.assistant_messages[0].thinking_content == "First thinking block"
            assert turn.assistant_messages[1].thinking_content == "Second thinking block"
        finally:
            session_jsonl.unlink()


class TestUserMessageImages:
    """Tests for parsing images from user messages."""

    def test_user_message_with_image_extracts_content(self):
        """User messages with images should have images extracted as Content objects."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image?"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": TINY_PNG_BASE64,
                            },
                        },
                    ],
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "I see a red pixel."}],
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            assert session is not None
            assert len(session.turns) == 1

            turn = session.turns[0]
            user_msg = turn.user_message

            # User message should have text content
            assert user_msg.content == "What's in this image?"

            # User message should have images list with Content objects
            assert hasattr(user_msg, "images"), "UserMessage should have 'images' attribute"
            assert len(user_msg.images) == 1

            image = user_msg.images[0]
            assert isinstance(image, Content)
            assert image.mimetype == "image/png"
            # Verify it's actual image data (PNG magic bytes after base64 decode)
            assert image.data[:4] == b"\x89PNG"
        finally:
            session_jsonl.unlink()

    def test_user_message_with_multiple_images(self):
        """User messages can contain multiple images."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Compare these images"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": TINY_PNG_BASE64,
                            },
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": TINY_PNG_BASE64,  # Using same data, mimetype is what matters
                            },
                        },
                    ],
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Both are red pixels."}],
                    "usage": {"input_tokens": 200, "output_tokens": 10},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            assert session is not None
            turn = session.turns[0]

            assert len(turn.user_message.images) == 2
            assert turn.user_message.images[0].mimetype == "image/png"
            assert turn.user_message.images[1].mimetype == "image/jpeg"
        finally:
            session_jsonl.unlink()

    def test_user_message_without_images_has_empty_list(self):
        """User messages without images should have empty images list."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "Just text, no images",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Got it."}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            assert session is not None
            turn = session.turns[0]

            assert hasattr(turn.user_message, "images")
            assert turn.user_message.images == []
        finally:
            session_jsonl.unlink()

    def test_user_message_with_text_as_list_no_images(self):
        """User messages with content as list but no images should have empty images list."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "First part"},
                        {"type": "text", "text": "Second part"},
                    ],
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Got both parts."}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            assert session is not None
            turn = session.turns[0]

            assert turn.user_message.content == "First part\nSecond part"
            assert turn.user_message.images == []
        finally:
            session_jsonl.unlink()


class TestSkillExpansionDetection:
    """Tests for detecting skill expansions and not creating new turns for them."""

    def test_skill_expansion_not_new_turn(self):
        """Messages starting with 'Base directory for this skill:' should not create turns."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Use the brainstorming skill"},
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
                            "name": "Skill",
                            "input": {"skill": "superpowers:brainstorming"},
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                },
            },
            # Skill expansion message - should NOT create a new turn
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "test-session",
                "sourceToolUseID": "tool-1",
                "isMeta": True,
                "message": {
                    "role": "user",
                    "content": "Base directory for this skill: /path/to/skill\n\n# Brainstorming\n\nThis is the skill content...",
                },
            },
            {
                "type": "assistant",
                "uuid": "a2",
                "timestamp": "2025-01-01T10:00:03Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "I understand the skill."}],
                    "usage": {"input_tokens": 200, "output_tokens": 20},
                },
            },
            # Real user message - should create a new turn
            {
                "type": "user",
                "uuid": "u3",
                "timestamp": "2025-01-01T10:00:04Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Now help me brainstorm"},
            },
            {
                "type": "assistant",
                "uuid": "a3",
                "timestamp": "2025-01-01T10:00:05Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Let me help you brainstorm."}],
                    "usage": {"input_tokens": 300, "output_tokens": 30},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            # Should have 2 turns, not 3
            # Turn 1: "Use the brainstorming skill" (with skill expansion as metadata)
            # Turn 2: "Now help me brainstorm"
            assert len(session.turns) == 2, f"Expected 2 turns, got {len(session.turns)}"
            assert "brainstorming skill" in session.turns[0].user_message.content
            assert "help me brainstorm" in session.turns[1].user_message.content

            # Turn 1 should have the skill expansion stored
            assert hasattr(session.turns[0], "skill_expansion")
            assert session.turns[0].skill_expansion is not None
            assert "Base directory for this skill:" in session.turns[0].skill_expansion
        finally:
            session_jsonl.unlink()

    def test_regular_user_message_not_skill_expansion(self):
        """Regular user messages should still create new turns."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "First question"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "First answer"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Second question"},
            },
            {
                "type": "assistant",
                "uuid": "a2",
                "timestamp": "2025-01-01T10:00:03Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Second answer"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            # Should have 2 turns - both are regular user messages
            assert len(session.turns) == 2
            assert session.turns[0].user_message.content == "First question"
            assert session.turns[1].user_message.content == "Second question"

            # Neither should have skill expansions
            assert session.turns[0].skill_expansion is None
            assert session.turns[1].skill_expansion is None
        finally:
            session_jsonl.unlink()


class TestGetCreatedAndModifiedFiles:
    """Tests for Session.get_created_files() and get_modified_files() methods."""

    def test_get_created_files_returns_files_from_write_without_backup(self):
        """get_created_files should return files created via Write tool that have no backup."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Create a new file"},
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Write",
                            "input": {
                                "file_path": "/path/to/new_file.py",
                                "content": "print('hello')",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            created = session.get_created_files()
            assert "/path/to/new_file.py" in created
            assert len(created) == 1
        finally:
            session_jsonl.unlink()

    def test_get_created_files_excludes_files_with_backup(self):
        """get_created_files should exclude files that have a backup (were modified, not created)."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Edit file"},
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Write",
                            "input": {
                                "file_path": "/path/to/existing.py",
                                "content": "modified content",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
            # File backup indicates this file existed before
            {
                "type": "file-history-snapshot",
                "snapshot": {
                    "messageId": "msg-2",
                    "trackedFileBackups": {
                        "/path/to/existing.py": {
                            "backupFileName": "abc123@v1",
                            "version": 1,
                            "backupTime": "2025-01-01T10:00:00Z",
                        }
                    },
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            created = session.get_created_files()
            # File has backup, so not "created"
            assert "/path/to/existing.py" not in created
            assert len(created) == 0
        finally:
            session_jsonl.unlink()

    def test_get_modified_files_returns_files_with_backup(self):
        """get_modified_files should return files that have backups."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Edit file"},
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Done"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
            {
                "type": "file-history-snapshot",
                "snapshot": {
                    "messageId": "msg-2",
                    "trackedFileBackups": {
                        "/path/to/modified.py": {
                            "backupFileName": "xyz789@v1",
                            "version": 1,
                            "backupTime": "2025-01-01T10:00:00Z",
                        }
                    },
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            modified = session.get_modified_files()
            assert "/path/to/modified.py" in modified
            assert len(modified) == 1
        finally:
            session_jsonl.unlink()

    def test_get_created_files_handles_multiple_writes_to_same_file(self):
        """Multiple writes to same new file should only appear once in created files."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Create and edit"},
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Write",
                            "input": {"file_path": "/new.py", "content": "v1"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool-2",
                            "name": "Write",
                            "input": {"file_path": "/new.py", "content": "v2"},
                        },
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            created = session.get_created_files()
            assert "/new.py" in created
            assert len(created) == 1  # Only one entry even though written twice
        finally:
            session_jsonl.unlink()

    def test_get_all_changed_files_combines_created_and_modified(self):
        """get_all_changed_files should return union of created and modified files."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Work on files"},
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Write",
                            "input": {"file_path": "/created.py", "content": "new"},
                        },
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
            {
                "type": "file-history-snapshot",
                "snapshot": {
                    "messageId": "msg-2",
                    "trackedFileBackups": {
                        "/modified.py": {
                            "backupFileName": "abc@v1",
                            "version": 1,
                            "backupTime": "2025-01-01T10:00:00Z",
                        }
                    },
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            all_changed = session.get_all_changed_files()
            assert "/created.py" in all_changed
            assert "/modified.py" in all_changed
            assert len(all_changed) == 2
        finally:
            session_jsonl.unlink()
