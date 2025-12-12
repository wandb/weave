"""Tests for Claude Code session parser."""

import json
import tempfile
from pathlib import Path

import pytest

from weave.integrations.claude_plugin.session_parser import (
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
