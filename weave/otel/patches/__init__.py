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

    # Claude Agent SDK: no media patch needed here — the Weave instrumentor
    # (weave.otel.instrumentors.claude_agent_sdk) handles tracing directly
    # via monkey-patching InternalClient.process_query.


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
