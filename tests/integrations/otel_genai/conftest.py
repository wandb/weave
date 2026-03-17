"""Shared fixtures for GenAI OTel integration tests.

OTel global state management:
The OTel SDK caches tracers by provider. Multiple agent SDKs (OpenAI, Google
ADK, Anthropic) cache their tracers at import or construction time. To ensure
each test gets a fresh exporter, we use a session-scoped TracerProvider and
swap the span processor per test via a function-scoped fixture.
"""

from collections.abc import Generator, Sequence
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from weave.trace_server import trace_server_interface as tsi

_SESSION_PROVIDER: TracerProvider | None = None


@pytest.fixture(scope="session", autouse=True)
def _otel_session_provider() -> Generator[TracerProvider, None, None]:
    """Set up a session-scoped TracerProvider as the global OTel provider.

    This runs once before any test in the otel_genai suite. All SDK modules
    that cache tracers at import time will pick up this provider.
    """
    global _SESSION_PROVIDER
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    _SESSION_PROVIDER = provider
    yield provider


@pytest.fixture
def fresh_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Create a fresh InMemorySpanExporter wired into the session provider.

    Adds a SimpleSpanProcessor to the session provider, yields the exporter,
    then removes the processor so the next test gets a clean slate.
    """
    assert _SESSION_PROVIDER is not None, "Session provider not initialized"

    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    _SESSION_PROVIDER.add_span_processor(processor)

    yield exporter

    processor.shutdown()


def build_genai_export_req(
    finished_spans: Sequence[ReadableSpan],
    project_id: str,
    wb_user_id: str = "test-user",
) -> tsi.OTelExportReq:
    """Convert InMemorySpanExporter spans into an OTelExportReq.

    Uses the OTLP proto encoder to convert ReadableSpan objects into protobuf
    ResourceSpans, then wraps them in the server's OTelExportReq format.
    This exercises the same protobuf parsing path as the real endpoint.
    """
    pb_request = encode_spans(finished_spans)

    processed_spans = []
    for resource_spans in pb_request.resource_spans:
        processed_spans.append(
            tsi.ProcessedResourceSpans(
                entity="test-entity",
                project="test-project",
                run_id=None,
                resource_spans=resource_spans,
            )
        )

    return tsi.OTelExportReq(
        project_id=project_id,
        processed_spans=processed_spans,
        wb_user_id=wb_user_id,
    )


def find_spans_by_field(
    spans: list[Any],
    field: str,
    value: str,
) -> list[Any]:
    """Filter spans where a field matches a value (case-insensitive for strings)."""
    results = []
    for span in spans:
        attr = getattr(span, field, None)
        if attr is not None and str(attr).lower() == str(value).lower():
            results.append(span)
    return results
