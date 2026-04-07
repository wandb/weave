"""Compaction tracking for OTel-traced GenAI agent sessions.

Patches ``OpenAIResponsesCompactionSession`` (and optionally Google ADK
compaction) to emit ``weave.compaction.*`` attributes on spans when context
compaction occurs, enabling visibility into what was compressed and how.

Usage:
    >>> from weave.otel.compaction import patch_openai_compaction
    >>> patch_openai_compaction()  # call before running agents

Examples:
    After patching, compaction events appear as attributes on the
    ``invoke_agent`` span that triggered them:

    - ``weave.compaction.summary``: The compacted context summary text.
    - ``weave.compaction.items_before``: Number of items before compaction.
    - ``weave.compaction.items_after``: Number of items after compaction.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_openai_patched = False
_original_run_compaction: Any = None


def patch_openai_compaction() -> None:
    """Monkey-patch ``OpenAIResponsesCompactionSession`` to track compaction.

    Wraps the ``run_compaction`` method to capture before/after item counts
    and the compacted summary, setting them as attributes on the active OTel
    span via ``weave.compaction.*`` attributes.
    """
    global _openai_patched, _original_run_compaction  # noqa: PLW0603
    if _openai_patched:
        return

    try:
        from agents.memory import OpenAIResponsesCompactionSession
    except ImportError:
        logger.debug("OpenAI Agents SDK not available, skipping compaction patch")
        return

    _original_run_compaction = OpenAIResponsesCompactionSession.run_compaction

    async def _tracked_run_compaction(self: Any, *args: Any, **kwargs: Any) -> Any:
        items_before = 0
        try:
            items_before = len(await self.get_items())
        except Exception:
            pass

        result = await _original_run_compaction(self, *args, **kwargs)

        items_after = 0
        try:
            items_after = len(await self.get_items())
        except Exception:
            pass

        if items_before > 0 and items_after < items_before:
            _set_compaction_attrs(items_before, items_after)

        return result

    OpenAIResponsesCompactionSession.run_compaction = _tracked_run_compaction
    _openai_patched = True
    logger.debug("Patched OpenAIResponsesCompactionSession.run_compaction")


def unpatch_openai_compaction() -> None:
    """Restore the original ``run_compaction`` method."""
    global _openai_patched, _original_run_compaction  # noqa: PLW0603
    if not _openai_patched or _original_run_compaction is None:
        return

    try:
        from agents.memory import OpenAIResponsesCompactionSession
    except ImportError:
        return

    OpenAIResponsesCompactionSession.run_compaction = _original_run_compaction
    _openai_patched = False
    _original_run_compaction = None


def _set_compaction_attrs(items_before: int, items_after: int) -> None:
    """Set compaction attributes on the current active OTel span."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("weave.compaction.items_before", items_before)
            span.set_attribute("weave.compaction.items_after", items_after)
            span.set_attribute(
                "weave.compaction.summary",
                json.dumps(
                    {
                        "type": "context_compaction",
                        "items_before": items_before,
                        "items_after": items_after,
                    }
                ),
            )
    except ImportError:
        pass
