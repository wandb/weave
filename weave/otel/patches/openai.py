"""Auto-capture media from OpenAI API calls.

Patches:
  - audio.speech.create -> captures TTS audio output
  - images.generate -> captures generated images
  - Responses API image_generation_call output items -> captures DALL-E images
"""

from __future__ import annotations

import base64
import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

_original_speech_create = None
_original_images_generate = None


def _capture_speech_output(response: Any) -> None:
    """Extract audio bytes from a TTS response and log them."""
    try:
        content = response.content if hasattr(response, "content") else None
        if content and isinstance(content, bytes):
            from weave.otel import log_content

            log_content(
                content, key="tts_audio", media_type="audio/mpeg", role="output"
            )
    except Exception:
        logger.debug("Failed to capture TTS audio", exc_info=True)


def _capture_image_b64(b64_data: str, key: str = "generated_image") -> None:
    """Decode base64 image data and log it."""
    try:
        image_bytes = base64.b64decode(b64_data)
        from weave.otel import log_content

        log_content(image_bytes, key=key, media_type="image/png", role="output")
    except Exception:
        logger.debug("Failed to capture image", exc_info=True)


def _capture_images_response(response: Any) -> None:
    """Extract images from an images.generate response."""
    try:
        data = getattr(response, "data", None)
        if not data:
            return
        for i, item in enumerate(data):
            b64 = getattr(item, "b64_json", None)
            if b64:
                key = f"generated_image_{i}" if len(data) > 1 else "generated_image"
                _capture_image_b64(b64, key=key)
            url = getattr(item, "url", None)
            if url and not b64:
                from weave.otel import (
                    _CONTENT_REFS_ATTR,
                    _append_to_span_attr,
                    _get_active_span,
                )

                span = _get_active_span()
                if span:
                    _append_to_span_attr(
                        span,
                        _CONTENT_REFS_ATTR,
                        {
                            "url": url,
                            "media_type": "image/png",
                            "role": "output",
                            "key": f"generated_image_{i}"
                            if len(data) > 1
                            else "generated_image",
                        },
                    )
    except Exception:
        logger.debug("Failed to capture images response", exc_info=True)


def patch() -> None:
    """Apply OpenAI media capture patches."""
    global _original_speech_create, _original_images_generate  # noqa: PLW0603

    try:
        import openai
    except ImportError:
        return

    if hasattr(openai, "resources") and hasattr(openai.resources, "audio"):
        speech_cls = openai.resources.audio.speech.Speech
        if _original_speech_create is None:
            _original_speech_create = speech_cls.create

            orig_speech = _original_speech_create

            @functools.wraps(orig_speech)
            def patched_speech_create(self: Any, *args: Any, **kwargs: Any) -> Any:
                response = orig_speech(self, *args, **kwargs)
                _capture_speech_output(response)
                return response

            speech_cls.create = patched_speech_create

    if hasattr(openai, "resources") and hasattr(openai.resources, "images"):
        images_cls = openai.resources.images.Images
        if _original_images_generate is None:
            _original_images_generate = images_cls.generate

            orig_images = _original_images_generate

            @functools.wraps(orig_images)
            def patched_images_generate(self: Any, *args: Any, **kwargs: Any) -> Any:
                if "response_format" not in kwargs:
                    kwargs["response_format"] = "b64_json"
                response = orig_images(self, *args, **kwargs)
                _capture_images_response(response)
                return response

            images_cls.generate = patched_images_generate


def unpatch() -> None:
    """Remove OpenAI media capture patches."""
    global _original_speech_create, _original_images_generate  # noqa: PLW0603

    try:
        import openai
    except ImportError:
        return

    if _original_speech_create is not None:
        openai.resources.audio.speech.Speech.create = _original_speech_create
        _original_speech_create = None

    if _original_images_generate is not None:
        openai.resources.images.Images.generate = _original_images_generate
        _original_images_generate = None
