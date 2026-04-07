"""Weave OTel instrumentor for Google ADK (Agent Development Kit).

Google ADK emits OTel spans natively.  This instrumentor **enriches** those
spans with attributes that ADK does not yet emit — system instructions,
tool definitions, and conversation tracking — by registering an OTel
``SpanProcessor`` on the ``TracerProvider``.

Usage::

    from google.adk.agents import LlmAgent
    from weave.otel import setup_tracing
    from weave.otel.instrumentors.google_adk import instrument

    provider = setup_tracing(project="my-project", genai_endpoint="...")
    coordinator = LlmAgent(name="Coordinator", ...)
    instrument(provider, agents=[coordinator], conversation="my-chat")

Dependencies:
    - ``google-adk`` (the Google Agent Development Kit)
    - ``opentelemetry-sdk``
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import LlmAgent
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider

logger = logging.getLogger(__name__)

_active_processor: WeaveADKSpanProcessor | None = None


# ---------------------------------------------------------------------------
# Agent discovery
# ---------------------------------------------------------------------------


@dataclass
class _AgentMeta:
    """Metadata extracted from an ``LlmAgent`` object."""

    name: str
    instructions: str = ""
    tool_defs: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""


def _discover_agents(agents: list[LlmAgent]) -> dict[str, _AgentMeta]:
    """Recursively walk the agent tree and extract metadata.

    Inspects ``LlmAgent.instruction``, ``LlmAgent.tools``,
    ``LlmAgent.sub_agents``, ``LlmAgent.model``, and
    ``LlmAgent.description`` on each agent, following ``sub_agents``
    references to discover the full agent graph.

    Args:
        agents: Root agent(s) to start discovery from.

    Returns:
        Dict mapping agent name to its extracted metadata.

    Examples:
        >>> meta = _discover_agents([coordinator])
        >>> meta["Coordinator"].instructions
        'You route requests to specialists.'
    """
    result: dict[str, _AgentMeta] = {}
    queue = list(agents)
    seen: set[str] = set()

    while queue:
        agent = queue.pop(0)
        name = getattr(agent, "name", None)
        if not name or name in seen:
            continue
        seen.add(name)

        instructions = ""
        raw = getattr(agent, "instruction", None)
        if isinstance(raw, str):
            instructions = raw

        tool_defs: list[dict[str, Any]] = []

        for tool in getattr(agent, "tools", []) or []:
            tool_name = getattr(tool, "__name__", None) or getattr(tool, "name", None)
            if not tool_name:
                continue
            tool_def: dict[str, Any] = {"type": "function", "name": tool_name}
            doc = getattr(tool, "__doc__", None) or getattr(tool, "description", None)
            if doc:
                first_line = doc.strip().split("\n")[0]
                tool_def["description"] = first_line
            tool_defs.append(tool_def)

        for sub in getattr(agent, "sub_agents", []) or []:
            s_name = getattr(sub, "name", "")
            s_desc = getattr(sub, "description", "")
            tool_defs.append(
                {"type": "sub_agent", "name": s_name, "description": s_desc}
            )
            queue.append(sub)

        model = str(getattr(agent, "model", "") or "")

        result[name] = _AgentMeta(
            name=name,
            instructions=instructions,
            tool_defs=tool_defs,
            model=model,
        )

    return result


# ---------------------------------------------------------------------------
# Agent name extraction from span names
# ---------------------------------------------------------------------------


def _extract_agent_name_from_span(span_name: str) -> str:
    """Parse agent name from ADK span naming patterns.

    ADK uses several span name formats:
    - ``invoke_agent Coordinator``
    - ``agent_run [WeatherAgent]``
    - ``Coordinator`` (bare agent name as root span)
    """
    lower = span_name.lower()
    if lower.startswith("invoke_agent "):
        return span_name[13:].strip()
    if span_name.startswith("agent_run [") and span_name.endswith("]"):
        return span_name[len("agent_run [") : -1]
    return span_name.strip()


# ---------------------------------------------------------------------------
# Core OTel SpanProcessor
# ---------------------------------------------------------------------------


class WeaveADKSpanProcessor(SpanProcessor):
    """SpanProcessor that enriches Google ADK's native OTel spans.

    Injects ``gen_ai.system_instructions``, ``gen_ai.tool.definitions``,
    and ``gen_ai.conversation.id/name`` on agent spans — attributes that
    ADK does not yet emit natively.

    Registered on the ``TracerProvider`` via ``instrument()``.
    """

    def __init__(
        self,
        agent_meta: dict[str, _AgentMeta],
        conversation_id: str,
        conversation_name: str,
    ) -> None:
        self._agent_meta = agent_meta
        self._conversation_id = conversation_id
        self._conversation_name = conversation_name
        self._disabled = False

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Enrich ADK spans with system instructions and tool definitions."""
        if self._disabled:
            return

        if self._conversation_id:
            span.set_attribute("gen_ai.conversation.id", self._conversation_id)
        if self._conversation_name:
            span.set_attribute("gen_ai.conversation.name", self._conversation_name)

        span_name = span.name or ""
        if not span_name:
            return

        for agent_name, meta in self._agent_meta.items():
            if agent_name in span_name:
                if meta.instructions:
                    span.set_attribute(
                        "gen_ai.system_instructions",
                        json.dumps([{"role": "system", "content": meta.instructions}]),
                    )
                if meta.tool_defs:
                    span.set_attribute(
                        "gen_ai.tool.definitions", json.dumps(meta.tool_defs)
                    )
                break

    def on_end(self, span: ReadableSpan) -> None:
        """No-op — ADK already sets usage, messages, and model on its spans."""

    def _on_ending(self, span: ReadableSpan) -> None:
        """No-op — required by some OTel SDK versions."""

    def shutdown(self) -> None:
        """No-op."""

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        """No-op."""
        return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def instrument(
    provider: TracerProvider,
    *,
    agents: list[LlmAgent] | None = None,
    conversation: str | None = None,
    conversation_id: str | None = None,
    capture_media: bool = True,
) -> WeaveADKSpanProcessor:
    """Instrument Google ADK to enrich its native OTel spans with Weave GenAI attributes.

    One call replaces ``SystemPromptInjector``, ``ToolDefinitionsInjector``,
    and ``ConversationIdInjector`` — all metadata is auto-discovered from the
    ``LlmAgent`` objects.

    Args:
        provider: The OTel ``TracerProvider`` that ADK emits spans to.
        agents: Root agent(s) for automatic metadata discovery.  When
            provided, system prompts and tool definitions are extracted
            from ``LlmAgent.instruction``, ``LlmAgent.tools``, and
            ``LlmAgent.sub_agents`` recursively.
        conversation: Human-readable conversation name for the UI.
            Also generates a UUID conversation_id automatically.
        conversation_id: Explicit conversation ID.  When omitted, a
            UUID is generated if *conversation* is set.
        capture_media: Auto-capture images from Gemini
            ``generate_content`` responses via ``weave.otel.patches.google``.

    Returns:
        The registered ``WeaveADKSpanProcessor`` (can be passed to
        ``uninstrument()`` for cleanup).

    Examples:
        >>> from weave.otel import setup_tracing
        >>> from weave.otel.instrumentors.google_adk import instrument
        >>> provider = setup_tracing(project="demo", genai_endpoint="...")
        >>> instrument(provider, agents=[coordinator], conversation="trip")
    """
    global _active_processor  # noqa: PLW0603

    agent_meta: dict[str, _AgentMeta] = {}
    if agents:
        agent_meta = _discover_agents(agents)

    conv_id = conversation_id or (str(uuid.uuid4()) if conversation else "")
    conv_name = conversation or ""

    processor = WeaveADKSpanProcessor(
        agent_meta=agent_meta,
        conversation_id=conv_id,
        conversation_name=conv_name,
    )

    provider.add_span_processor(processor)
    _active_processor = processor

    if capture_media:
        try:
            from weave.otel.patches import google as google_patch

            google_patch.patch()
        except Exception:
            logger.debug("Failed to apply Google media capture patch", exc_info=True)

    if conv_name and conv_id:
        _write_conversation_annotation(conv_id, conv_name)

    return processor


def uninstrument(processor: WeaveADKSpanProcessor | None = None) -> None:
    """Disable the Weave ADK span processor.

    Args:
        processor: The processor returned by ``instrument()``.  When
            omitted, disables the most recently created processor.

    Examples:
        >>> proc = instrument(provider, agents=[coordinator])
        >>> uninstrument(proc)
    """
    global _active_processor  # noqa: PLW0603

    target = processor or _active_processor
    if target is not None:
        target._disabled = True

    if target is _active_processor:
        _active_processor = None

    try:
        from weave.otel.patches import google as google_patch

        google_patch.unpatch()
    except Exception:
        pass


def _write_conversation_annotation(conv_id: str, conv_name: str) -> None:
    """Write conversation name as an entity annotation (fire-and-forget)."""
    import os
    import threading

    def _post() -> None:
        try:
            import requests as http_requests

            endpoint = os.environ.get("WF_TRACE_SERVER_URL", "")
            if not endpoint:
                return
            api_key = os.environ.get("WANDB_API_KEY", "")
            entity = os.environ.get("WANDB_ENTITY", "")
            project = os.environ.get("WANDB_PROJECT", "")
            if not entity or not project:
                return

            url = f"{endpoint}/genai/annotations/upsert"
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if api_key:
                headers["wandb-api-key"] = api_key
            payload = {
                "project_id": f"{entity}/{project}",
                "annotations": [
                    {
                        "entity_type": "conversation",
                        "entity_id": conv_id,
                        "namespace": "display",
                        "key": "name",
                        "string_value": conv_name,
                        "value_type": "string",
                        "source": "sdk",
                    }
                ],
            }
            http_requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_post, daemon=True).start()
