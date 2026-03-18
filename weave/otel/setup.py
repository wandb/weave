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
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

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
            "service.version": "0.1.0",
            "wandb.entity": resolved_entity,
            "wandb.project": project,
        }
    )
    provider = TracerProvider(resource=resource)

    for proc in processors or []:
        provider.add_span_processor(proc)

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
