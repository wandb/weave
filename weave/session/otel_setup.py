"""TracerProvider lifecycle for the Weave Session SDK.

All opentelemetry imports are lazy (inside functions) so this module
can be imported even when opentelemetry is not installed.
"""

from __future__ import annotations

from typing import Any

_TRACER_NAME = "weave.session"
_provider: Any = None  # TracerProvider | None


def setup_tracer_provider(
    *,
    endpoint: str,
    api_key: str = "",
    service_name: str = "weave-session-sdk",
    entity: str = "",
    project: str = "",
) -> None:
    """Configure the module-level TracerProvider with an OTLP HTTP exporter.

    Calling again replaces the previous provider (shuts it down first).
    """
    global _provider  # noqa: PLW0603
    if _provider is not None:
        _provider.shutdown()

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    headers: dict[str, str] = {}
    if api_key:
        headers["authorization"] = f"Basic {api_key}"

    resource_attrs: dict[str, str] = {"service.name": service_name}
    if entity:
        resource_attrs["wandb.entity"] = entity
    if project:
        resource_attrs["wandb.project"] = project

    resource = Resource.create(resource_attrs)
    exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
    processor = BatchSpanProcessor(exporter)

    _provider = TracerProvider(resource=resource)
    _provider.add_span_processor(processor)


def get_tracer() -> Any:
    """Return a Tracer from the current provider, or a no-op tracer."""
    from opentelemetry import trace

    if _provider is not None:
        return _provider.get_tracer(_TRACER_NAME)
    return trace.get_tracer(_TRACER_NAME)


def reset_tracer_provider() -> None:
    """Shut down and clear the module-level TracerProvider."""
    global _provider  # noqa: PLW0603
    if _provider is not None:
        _provider.shutdown()
        _provider = None
