"""Auto-capture media from Google Gemini / ADK API calls.

Patches generate_content responses to capture inline_data (images, audio)
from content parts.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

_original_generate_content = None
_original_generate_content_async = None


def _capture_inline_data(response: Any) -> None:
    """Extract inline_data from Gemini response parts and log them."""
    try:
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return

        from weave.otel import log_content

        idx = 0
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", None)
            if not parts:
                continue
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data:
                    data_bytes = getattr(inline_data, "data", None)
                    mime_type = getattr(
                        inline_data, "mime_type", "application/octet-stream"
                    )
                    if data_bytes and isinstance(data_bytes, bytes):
                        key = f"gemini_media_{idx}" if idx > 0 else "gemini_media"
                        log_content(
                            data_bytes, key=key, media_type=mime_type, role="output"
                        )
                        idx += 1
    except Exception:
        logger.debug("Failed to capture Gemini inline_data", exc_info=True)


def patch() -> None:
    """Apply Google Gemini media capture patches."""
    global _original_generate_content, _original_generate_content_async  # noqa: PLW0603

    try:
        from google.genai import models
    except ImportError:
        return

    model_cls = getattr(models, "Models", None) or getattr(
        models, "GenerativeModel", None
    )
    if model_cls is None:
        return

    if hasattr(model_cls, "generate_content") and _original_generate_content is None:
        _original_generate_content = model_cls.generate_content

        orig_sync = _original_generate_content

        @functools.wraps(orig_sync)
        def patched_generate_content(self: Any, *args: Any, **kwargs: Any) -> Any:
            response = orig_sync(self, *args, **kwargs)
            _capture_inline_data(response)
            return response

        model_cls.generate_content = patched_generate_content

    if (
        hasattr(model_cls, "generate_content_async")
        and _original_generate_content_async is None
    ):
        _original_generate_content_async = model_cls.generate_content_async

        orig_async = _original_generate_content_async

        @functools.wraps(orig_async)
        async def patched_generate_content_async(
            self: Any, *args: Any, **kwargs: Any
        ) -> Any:
            response = await orig_async(self, *args, **kwargs)
            _capture_inline_data(response)
            return response

        model_cls.generate_content_async = patched_generate_content_async


def unpatch() -> None:
    """Remove Google Gemini media capture patches."""
    global _original_generate_content, _original_generate_content_async  # noqa: PLW0603

    try:
        from google.genai import models
    except ImportError:
        return

    model_cls = getattr(models, "Models", None) or getattr(
        models, "GenerativeModel", None
    )
    if model_cls is None:
        return

    if _original_generate_content is not None:
        model_cls.generate_content = _original_generate_content
        _original_generate_content = None

    if _original_generate_content_async is not None:
        model_cls.generate_content_async = _original_generate_content_async
        _original_generate_content_async = None
