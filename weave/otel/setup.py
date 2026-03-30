"""OTel TracerProvider setup and span processors for Weave GenAI tracing.

Provides a one-call ``setup_tracing()`` that configures exporters, live span
streaming, and system-prompt injection — replacing ~80 lines of boilerplate
in every example script.

Examples:
    >>> from weave.otel import setup_tracing, SystemPromptInjector
    >>> provider = setup_tracing(
    ...     service_name="my-agent",
    ...     project="my-project",
    ...     genai_endpoint="http://localhost:6345/otel/v1/genai/traces",
    ...     processors=[SystemPromptInjector({"AgentA": "You are helpful."})],
    ... )
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from weave.version import VERSION

logger = logging.getLogger(__name__)

__all__ = ["SystemPromptInjector", "setup_tracing"]


class SystemPromptInjector:
    """SpanProcessor that injects ``gen_ai.system_instructions`` on agent spans.

    The OTel GenAI semantic conventions define ``gen_ai.system_instructions``
    (merged in semantic-conventions PR #2179, Aug 2025) but no instrumentor
    emits it yet.  This processor fills the gap by matching span names to
    a dict of agent-name -> instructions.

    Args:
        agent_instructions: Mapping of agent name to its system prompt string.
            Matching is done by checking if the agent name appears anywhere in
            the span name (e.g. ``"invoke_agent TriageAgent"`` matches key
            ``"TriageAgent"``).

    Examples:
        >>> from weave.otel import SystemPromptInjector
        >>> injector = SystemPromptInjector({
        ...     "TriageAgent": "You route requests to specialists.",
        ...     "WeatherBot": "You report weather using the get_weather tool.",
        ... })
    """

    def __init__(self, agent_instructions: dict[str, str]) -> None:
        self._instructions = agent_instructions

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        """Set system_instructions if the span name matches a known agent."""
        name = span.name or ""
        for agent_name, instructions in self._instructions.items():
            if agent_name in name:
                span.set_attribute(
                    "gen_ai.system_instructions",
                    json.dumps([{"role": "system", "content": instructions}]),
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


class ConversationIdInjector:
    """SpanProcessor that sets ``gen_ai.conversation.id`` and optionally
    ``gen_ai.conversation.name`` on every span.

    Ensures each conversation gets a globally unique ID (UUID4 by default)
    and an optional human-readable display name. When a name is provided,
    it is also written as an entity annotation to the Weave annotations API.

    Args:
        name: Human-readable conversation name (e.g. "trip-planning").
            Set as ``gen_ai.conversation.name`` on every span.
        id: Explicit conversation ID. When omitted a UUID4 is generated
            automatically, guaranteeing uniqueness across runs.

    Examples:
        >>> from weave.otel import ConversationIdInjector
        >>> ConversationIdInjector(name="trip-planning")
        >>> ConversationIdInjector(id="my-uuid", name="trip-planning")
        >>> ConversationIdInjector()
    """

    def __init__(self, *, name: str = "", id: str = "") -> None:
        self._id = id or str(uuid.uuid4())
        self._name = name
        self._annotation_written = False

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        """Set gen_ai.conversation.id and optionally gen_ai.conversation.name."""
        span.set_attribute("gen_ai.conversation.id", self._id)
        if self._name:
            span.set_attribute("gen_ai.conversation.name", self._name)
            if not self._annotation_written:
                self._annotation_written = True
                self._write_annotation()

    def _write_annotation(self) -> None:
        """Write conversation name as an annotation (fire-and-forget, background thread)."""
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
                            "entity_id": self._id,
                            "namespace": "display",
                            "key": "name",
                            "string_value": self._name,
                            "value_type": "string",
                            "source": "sdk",
                        }
                    ],
                }
                http_requests.post(url, json=payload, headers=headers, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_post, daemon=True).start()

    def on_end(self, span: Any) -> None:
        """No-op."""

    def _on_ending(self, span: Any) -> None:
        """No-op — required by some OTel SDK versions."""

    def shutdown(self) -> None:
        """No-op."""

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        """No-op."""
        return True


def _wandb_auth_headers() -> dict[str, str]:
    """Build auth headers from ``WANDB_API_KEY`` if present."""
    api_key = os.environ.get("WANDB_API_KEY", "")
    if api_key:
        return {"wandb-api-key": api_key}
    return {}


def setup_tracing(
    *,
    service_name: str = "weave-genai",
    project: str = "genai-otel",
    entity: str | None = None,
    genai_endpoint: str | None = None,
    otlp_endpoint: str | None = None,
    processors: list[Any] | None = None,
    enable_live: bool = True,
) -> TracerProvider:
    """Configure and install an OTel TracerProvider for GenAI tracing.

    Handles resource creation, exporter selection, optional live-span
    streaming, and any extra span processors (e.g. ``SystemPromptInjector``).

    Args:
        service_name: ``service.name`` resource attribute.
        project: W&B project name (set as ``wandb.project``).
        entity: W&B entity. Defaults to ``$WANDB_ENTITY``.
        genai_endpoint: Weave GenAI OTLP/HTTP endpoint
            (e.g. ``http://host:6345/otel/v1/genai/traces``).  When provided
            a ``LiveSpanProcessor`` is also registered.
        otlp_endpoint: Plain OTLP/gRPC endpoint (mutually exclusive with
            *genai_endpoint*).
        processors: Extra ``SpanProcessor`` instances to register before the
            export processors.
        enable_live: Whether to add a ``LiveSpanProcessor`` when
            *genai_endpoint* is set.  Defaults to ``True``.

    Returns:
        The configured ``TracerProvider`` (already set as the global provider).

    Examples:
        >>> provider = setup_tracing(
        ...     service_name="my-agent",
        ...     project="demo",
        ...     genai_endpoint="http://localhost:6345/otel/v1/genai/traces",
        ... )
    """
    resolved_entity = entity or os.environ.get("WANDB_ENTITY", "")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": VERSION,
            "wandb.entity": resolved_entity,
            "wandb.project": project,
        }
    )
    provider = TracerProvider(resource=resource)

    for proc in processors or []:
        provider.add_span_processor(proc)

    if not genai_endpoint:
        wf_url = os.environ.get("WF_TRACE_SERVER_URL", "")
        if wf_url:
            genai_endpoint = f"{wf_url.rstrip('/')}/otel/v1/genai/traces"
            logger.debug("Auto-detected genai_endpoint from WF_TRACE_SERVER_URL: %s", genai_endpoint)

    if genai_endpoint:
        if enable_live:
            from weave.otel.live_processor import LiveSpanProcessor

            server_url = genai_endpoint.rsplit("/otel/", 1)[0]
            provider.add_span_processor(
                LiveSpanProcessor(
                    endpoint=f"{server_url}/otel/v1/genai/span/start",
                    headers=_wandb_auth_headers(),
                )
            )

        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as OTLPHTTPSpanExporter,
        )

        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPHTTPSpanExporter(
                    endpoint=genai_endpoint,
                    headers=_wandb_auth_headers(),
                )
            )
        )
    elif otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider
