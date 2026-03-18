"""Media capture patches for GenAI SDK integrations.

Call ``patch_all()`` to enable auto-capture for all available SDKs,
or import individual patch modules (``openai``, ``google``, ``anthropic``)
for selective patching.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def patch_all() -> None:
    """Enable media capture patches for all available SDKs."""
    try:
        from weave.otel.patches import openai as openai_patch

        openai_patch.patch()
    except Exception:
        logger.debug("OpenAI media patch skipped", exc_info=True)

    try:
        from weave.otel.patches import google as google_patch

        google_patch.patch()
    except Exception:
        logger.debug("Google media patch skipped", exc_info=True)

    # Anthropic patch omitted — official OTel Claude Agent SDK instrumentation
    # is still in development:
    # https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-claude-agent-sdk


def unpatch_all() -> None:
    """Remove all media capture patches."""
    try:
        from weave.otel.patches import openai as openai_patch

        openai_patch.unpatch()
    except Exception:
        pass

    try:
        from weave.otel.patches import google as google_patch

        google_patch.unpatch()
    except Exception:
        pass

