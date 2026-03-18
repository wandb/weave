"""Auto-capture media from Anthropic API calls.

Patches messages.create to capture base64 image content from both
requests (user-supplied images) and responses (if any).
"""

from __future__ import annotations

import base64
import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

_original_messages_create = None
_original_messages_create_async = None


def _capture_request_images(kwargs: dict[str, Any]) -> None:
    """Scan request messages for base64 image content blocks."""
    try:
        messages = kwargs.get("messages", [])
        if not messages:
            return

        from weave.otel import log_content

        idx = 0
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        b64_data = source.get("data", "")
                        media_type = source.get("media_type", "image/png")
                        if b64_data:
                            image_bytes = base64.b64decode(b64_data)
                            key = f"input_image_{idx}" if idx > 0 else "input_image"
                            log_content(
                                image_bytes,
                                key=key,
                                media_type=media_type,
                                role="input",
                            )
                            idx += 1
    except Exception:
        logger.debug("Failed to capture Anthropic request images", exc_info=True)


def patch() -> None:
    """Apply Anthropic media capture patches."""
    global _original_messages_create, _original_messages_create_async

    try:
        import anthropic
    except ImportError:
        return

    messages_cls = anthropic.resources.messages.Messages
    if _original_messages_create is None and hasattr(messages_cls, "create"):
        _original_messages_create = messages_cls.create

        @functools.wraps(_original_messages_create)
        def patched_create(self, *args, **kwargs):
            _capture_request_images(kwargs)
            return _original_messages_create(self, *args, **kwargs)

        messages_cls.create = patched_create

    async_messages_cls = anthropic.resources.messages.AsyncMessages
    if _original_messages_create_async is None and hasattr(async_messages_cls, "create"):
        _original_messages_create_async = async_messages_cls.create

        @functools.wraps(_original_messages_create_async)
        async def patched_create_async(self, *args, **kwargs):
            _capture_request_images(kwargs)
            return await _original_messages_create_async(self, *args, **kwargs)

        async_messages_cls.create = patched_create_async


def unpatch() -> None:
    """Remove Anthropic media capture patches."""
    global _original_messages_create, _original_messages_create_async

    try:
        import anthropic
    except ImportError:
        return

    if _original_messages_create is not None:
        anthropic.resources.messages.Messages.create = _original_messages_create
        _original_messages_create = None

    if _original_messages_create_async is not None:
        anthropic.resources.messages.AsyncMessages.create = _original_messages_create_async
        _original_messages_create_async = None
