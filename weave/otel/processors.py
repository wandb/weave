"""Custom OTel SpanProcessors for enriching GenAI spans.

Provides processors to fill gaps where upstream instrumentors don't emit
certain semantic convention attributes:

- ``ToolDefinitionsInjector``: sets ``gen_ai.tool.definitions`` on agent spans.
- ``patch_openai_reasoning``: monkey-patches the OpenAI Responses API to
  capture ``output_tokens_details.reasoning_tokens`` onto the active OTel span.

Note on o4-mini / o3 reasoning content:
    OpenAI encrypts reasoning content for o4-mini and most o3 variants —
    ``ResponseReasoningItem.content`` is ``None``.  Only ``reasoning_tokens``
    (the count) is available.  This is an OpenAI policy decision; we capture
    the count so Weave can display it even if the text is unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_openai_reasoning_patched = False
_original_responses_create: Any = None
_original_responses_create_async: Any = None


class ToolDefinitionsInjector:
    """SpanProcessor that injects ``gen_ai.tool.definitions`` on agent spans.

    The OTel semconv defines ``gen_ai.tool.definitions`` as Opt-In; most
    instrumentors skip it.  This processor fills the gap by matching
    span names to a dict of agent-name -> tool definitions JSON.

    Args:
        agent_tools: Mapping of agent name to its list of tool definition
            dicts.  Matching checks if the agent name appears in the span
            name (e.g. ``"invoke_agent TriageAgent"`` matches ``"TriageAgent"``).

    Examples:
        >>> injector = ToolDefinitionsInjector({
        ...     "WeatherBot": [{"type": "function", "name": "get_weather", ...}],
        ... })
    """

    def __init__(self, agent_tools: dict[str, list[dict[str, Any]]]) -> None:
        self._agent_tools = agent_tools

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        """Set tool_definitions if the span name matches a known agent."""
        name = span.name or ""
        for agent_name, tools in self._agent_tools.items():
            if agent_name in name:
                span.set_attribute(
                    "gen_ai.tool.definitions",
                    json.dumps(tools),
                )
                break

    def on_end(self, span: Any) -> None:
        """No-op."""

    def _on_ending(self, span: Any) -> None:
        """No-op — required by some OTel SDK versions."""

    def shutdown(self) -> None:
        """No-op."""

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        """No-op."""
        return True


def _set_reasoning_tokens_on_span(reasoning_tokens: int) -> None:
    """Set gen_ai.usage.reasoning_tokens on the current active OTel span."""
    if reasoning_tokens <= 0:
        return
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("gen_ai.usage.reasoning_tokens", reasoning_tokens)
    except ImportError:
        pass


def patch_openai_reasoning() -> None:
    """Monkey-patch the OpenAI Responses API to capture reasoning token counts.

    The ``opentelemetry-instrumentation-openai-agents-v2`` instrumentor does
    not capture ``output_tokens_details.reasoning_tokens`` from the OpenAI
    Responses API response.  This patch wraps both the sync and async
    ``responses.create`` methods to read the token count and set it as
    ``gen_ai.usage.reasoning_tokens`` on the active OTel span.

    Call this before running agents, after setting up the TracerProvider.

    Note on reasoning content:
        OpenAI encrypts the chain-of-thought for o4-mini/o3 models — the
        ``ResponseReasoningItem.content`` field is ``None``.  Only the token
        count is available, which is what this patch captures.

    Examples:
        >>> from weave.otel.processors import patch_openai_reasoning
        >>> patch_openai_reasoning()
    """
    global _openai_reasoning_patched, _original_responses_create, _original_responses_create_async  # noqa: PLW0603
    if _openai_reasoning_patched:
        return

    try:
        import openai.resources.responses.responses as _resp_module
    except ImportError:
        logger.debug("openai not available, skipping reasoning token patch")
        return

    _original_responses_create = _resp_module.Responses.create
    _original_responses_create_async = _resp_module.AsyncResponses.create

    def _patched_create(self_inner: Any, *args: Any, **kwargs: Any) -> Any:
        result = _original_responses_create(self_inner, *args, **kwargs)
        _extract_reasoning_from_response(result)
        return result

    async def _patched_create_async(self_inner: Any, *args: Any, **kwargs: Any) -> Any:
        result = await _original_responses_create_async(self_inner, *args, **kwargs)
        _extract_reasoning_from_response(result)
        return result

    _resp_module.Responses.create = _patched_create
    _resp_module.AsyncResponses.create = _patched_create_async
    _openai_reasoning_patched = True
    logger.debug("Patched OpenAI Responses.create for reasoning token extraction")


def unpatch_openai_reasoning() -> None:
    """Restore the original OpenAI Responses.create methods."""
    global _openai_reasoning_patched  # noqa: PLW0603
    if not _openai_reasoning_patched:
        return
    try:
        import openai.resources.responses.responses as _resp_module

        if _original_responses_create is not None:
            _resp_module.Responses.create = _original_responses_create
        if _original_responses_create_async is not None:
            _resp_module.AsyncResponses.create = _original_responses_create_async
    except ImportError:
        pass
    _openai_reasoning_patched = False


def _extract_reasoning_from_response(response: Any) -> None:
    """Read reasoning_tokens from an OpenAI Response object and stamp the span."""
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        details = getattr(usage, "output_tokens_details", None)
        if details is None:
            return
        reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0
        if reasoning_tokens > 0:
            _set_reasoning_tokens_on_span(reasoning_tokens)
    except Exception:
        pass
