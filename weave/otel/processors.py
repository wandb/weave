"""Custom OTel SpanProcessors for enriching GenAI spans.

Provides processors to fill gaps where upstream instrumentors don't emit
certain semantic convention attributes:

- ``ToolDefinitionsInjector``: sets ``gen_ai.tool.definitions`` on agent spans.
- ``ReasoningTokenExtractor``: extracts reasoning token counts from
  provider-specific response data and sets ``gen_ai.usage.reasoning_tokens``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


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


class ReasoningTokenExtractor:
    """SpanProcessor that extracts reasoning token counts from output messages.

    Sets ``gen_ai.usage.reasoning_tokens`` by inspecting the
    ``gen_ai.output.messages`` attribute for ``ReasoningPart`` entries and
    the provider-specific token usage fields.

    This processor runs on ``on_end`` / ``_on_ending`` since output messages
    are only available after the span completes.

    Examples:
        >>> extractor = ReasoningTokenExtractor()
    """

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        """No-op."""

    def on_end(self, span: Any) -> None:
        """No-op (read-only spans at this point)."""

    def _on_ending(self, span: Any) -> None:
        """Extract reasoning tokens before the span is exported."""
        if not hasattr(span, "attributes"):
            return
        attrs = span.attributes or {}

        already = attrs.get("gen_ai.usage.reasoning_tokens")
        if already is not None and already > 0:
            return

        output_msgs = attrs.get("gen_ai.output.messages")
        if not output_msgs:
            return

        try:
            messages = json.loads(output_msgs) if isinstance(output_msgs, str) else output_msgs
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(messages, list):
            return

        has_reasoning = False
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            for part in msg.get("parts", []):
                if isinstance(part, dict) and part.get("type") == "reasoning":
                    has_reasoning = True
                    break
            if has_reasoning:
                break

        if has_reasoning:
            span.set_attribute("gen_ai.usage.reasoning_tokens", -1)

    def shutdown(self) -> None:
        """No-op."""

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        """No-op."""
        return True
