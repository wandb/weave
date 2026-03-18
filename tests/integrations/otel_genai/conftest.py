"""Shared fixtures for OTel GenAI integration tests.

Provides an OTel TracerProvider with InMemorySpanExporter so tests can
collect spans produced by real SDK instrumentations (replayed via VCR),
then run them through the extraction + chat view pipeline.
"""

from __future__ import annotations

import datetime
from collections.abc import Generator
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.trace_server.opentelemetry.genai_extraction import extract_genai_fields
from weave.trace_server.opentelemetry.python_spans import Span as WeaveSpan
from weave.trace_server.trace_server_interface import GenAISpanSchema


@pytest.fixture
def otel_setup() -> Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]:
    """Set up an OTel TracerProvider with InMemorySpanExporter.

    Yields (provider, exporter) so tests can flush and read spans.
    Resets the global tracer provider on teardown.
    """
    exporter = InMemorySpanExporter()
    resource = Resource.create({
        "service.name": "otel-genai-test",
        "wandb.entity": "test-entity",
        "wandb.project": "test-project",
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield provider, exporter
    provider.shutdown()


def otel_spans_to_genai_schemas(
    exporter: InMemorySpanExporter,
    project_id: str = "test-entity/test-project",
) -> list[GenAISpanSchema]:
    """Convert collected OTel spans to GenAISpanSchema rows.

    This mirrors the ingest pipeline: OTel protobuf -> extract_genai_fields.
    Since we have in-memory ReadableSpan objects (not protobuf), we convert
    them to our internal Span format first.
    """
    schemas: list[GenAISpanSchema] = []
    for otel_span in exporter.get_finished_spans():
        ctx = otel_span.context
        if ctx is None:
            continue
        weave_span = _readable_span_to_weave_span(otel_span)
        schema = extract_genai_fields(weave_span, project_id)
        schemas.append(GenAISpanSchema(**schema.model_dump()))
    return schemas


def _readable_span_to_weave_span(otel_span: Any) -> WeaveSpan:
    """Convert an OTel SDK ReadableSpan to our internal Span representation."""
    from opentelemetry.sdk.trace import StatusCode
    from opentelemetry.trace import SpanKind

    from weave.trace_server.opentelemetry.python_spans import (
        Event,
        Status,
        StatusCodeEnum,
    )
    from weave.trace_server.opentelemetry.python_spans import (
        Resource as WeaveResource,
    )
    from weave.trace_server.opentelemetry.python_spans import (
        Span as WeaveSpan,
    )

    ctx = otel_span.context
    trace_id = format(ctx.trace_id, "032x")
    span_id = format(ctx.span_id, "016x")

    parent_id = ""
    if otel_span.parent and hasattr(otel_span.parent, "span_id"):
        parent_id = format(otel_span.parent.span_id, "016x")

    kind_map = {
        SpanKind.INTERNAL: "INTERNAL",
        SpanKind.SERVER: "SERVER",
        SpanKind.CLIENT: "CLIENT",
        SpanKind.PRODUCER: "PRODUCER",
        SpanKind.CONSUMER: "CONSUMER",
    }

    status_map = {
        StatusCode.UNSET: StatusCodeEnum.UNSET,
        StatusCode.OK: StatusCodeEnum.OK,
        StatusCode.ERROR: StatusCodeEnum.ERROR,
    }

    attrs = dict(otel_span.attributes) if otel_span.attributes else {}

    events = []
    for e in otel_span.events or []:
        events.append(Event(
            name=e.name,
            timestamp=datetime.datetime.fromtimestamp(e.timestamp / 1e9, tz=datetime.timezone.utc) if e.timestamp else None,
            attributes=dict(e.attributes) if e.attributes else {},
        ))

    resource_attrs = dict(otel_span.resource.attributes) if otel_span.resource else {}

    start_time = datetime.datetime.fromtimestamp(
        otel_span.start_time / 1e9, tz=datetime.timezone.utc
    ) if otel_span.start_time else None

    end_time = datetime.datetime.fromtimestamp(
        otel_span.end_time / 1e9, tz=datetime.timezone.utc
    ) if otel_span.end_time else None

    return WeaveSpan(
        trace_id=trace_id,
        span_id=span_id,
        parent_id=parent_id,
        name=otel_span.name or "",
        kind=SpanKind(otel_span.kind) if otel_span.kind is not None else SpanKind.INTERNAL,
        start_time=start_time,
        end_time=end_time,
        status=Status(
            code=status_map.get(otel_span.status.status_code, StatusCodeEnum.UNSET),
            message=otel_span.status.description or "",
        ),
        attributes=attrs,
        events=events,
        resource=WeaveResource(attributes=resource_attrs),
    )
