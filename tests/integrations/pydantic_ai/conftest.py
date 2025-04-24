"""
Fixtures and utilities for PydanticAI integration tests.

This module provides pytest fixtures and helper classes for testing the PydanticAI
integration with Weave's tracing and OpenTelemetry export functionality. It includes
mock exporters, span conversion utilities, and context managers for creating test clients
with patched exporters to avoid real network calls during tests.
"""

import contextlib
from typing import Any, Callable, Generator, Optional
from unittest.mock import patch

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import (
    KeyValue,
    InstrumentationScope,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
)
from opentelemetry.sdk.trace.export import SpanExportResult

from weave.integrations.pydantic_ai.utils import PydanticAISpanExporter
from weave.trace_server import trace_server_interface as tsi


class MockOTLPExporter:
    """
    Mock OTLP exporter that captures spans and forwards to the test server.

    This class mimics the interface of a real OTLP exporter but only stores
    exported spans in memory for inspection during tests.
    """

    def __init__(self) -> None:
        """Initialize the mock exporter with an empty list of exported spans."""
        self.exported_spans: list[Any] = []

    def export(self, spans: list[Any]) -> SpanExportResult:
        """
        Store spans for inspection.

        Args:
            spans: List of spans to export.

        Returns:
            SpanExportResult: Always returns SUCCESS.
        """
        self.exported_spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """No-op shutdown method for compatibility."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        No-op force flush method for compatibility.

        Args:
            timeout_millis: Timeout in milliseconds (unused).

        Returns:
            bool: Always returns True.
        """
        return True


def convert_readable_span_to_proto_span(readable_span: Any) -> Span:
    """
    Convert a ReadableSpan object to a protobuf Span object.

    This function handles:
    - Converting trace and span IDs from hex or int to bytes
    - Copying timestamps, kind, and attributes
    - Handling status codes and messages
    - Mapping all relevant fields from the ReadableSpan to the protobuf Span

    Args:
        readable_span: The ReadableSpan instance to convert.

    Returns:
        Span: The corresponding protobuf Span object.
    """
    proto_span = Span()
    proto_span.name = readable_span.name

    # Handle trace_id and span_id conversion (hex string or int to bytes)
    if hasattr(readable_span.context, "trace_id"):
        trace_id = readable_span.context.trace_id
        if isinstance(trace_id, str):
            proto_span.trace_id = bytes.fromhex(trace_id)
        else:
            proto_span.trace_id = trace_id.to_bytes(16, byteorder="big")

    if hasattr(readable_span.context, "span_id"):
        span_id = readable_span.context.span_id
        if isinstance(span_id, str):
            proto_span.span_id = bytes.fromhex(span_id)
        else:
            proto_span.span_id = span_id.to_bytes(8, byteorder="big")

    proto_span.start_time_unix_nano = readable_span.start_time
    proto_span.end_time_unix_nano = readable_span.end_time

    # Set span kind, defaulting to INTERNAL if not present
    if hasattr(readable_span, "kind"):
        span_kind = getattr(readable_span, "kind")
        if hasattr(span_kind, "value"):
            proto_span.kind = span_kind.value
        else:
            proto_span.kind = span_kind
    else:
        proto_span.kind = 1  # INTERNAL

    # Copy all attributes, handling lists/tuples as arrays
    for key, value in readable_span.attributes.items():
        kv = KeyValue()
        kv.key = key
        if isinstance(value, str):
            kv.value.string_value = value
        elif isinstance(value, int):
            kv.value.int_value = value
        elif isinstance(value, float):
            kv.value.double_value = value
        elif isinstance(value, bool):
            kv.value.bool_value = value
        elif isinstance(value, (list, tuple)):
            # Convert each item in the list/tuple to the appropriate type
            array_value = kv.value.array_value
            for item in value:
                val = array_value.values.add()
                if isinstance(item, str):
                    val.string_value = item
                elif isinstance(item, int):
                    val.int_value = item
                elif isinstance(item, float):
                    val.double_value = item
                elif isinstance(item, bool):
                    val.bool_value = item
        proto_span.attributes.append(kv)

    # Set status code and message if present
    if hasattr(readable_span, "status"):
        status_code = getattr(readable_span.status, "code", 0)
        if hasattr(status_code, "value"):
            proto_span.status.code = status_code.value
        else:
            proto_span.status.code = status_code
        status_msg = getattr(readable_span.status, "description", "")
        if status_msg is None:
            status_msg = ""
        proto_span.status.message = str(status_msg)

    return proto_span


@pytest.fixture
def pydantic_ai_client(client: Any, monkeypatch: Any) -> Any:
    """
    Fixture that provides a client with mocked PydanticAISpanExporter for testing.

    This avoids making real OTLP HTTP requests during tests while preserving
    the original processing logic of the PydanticAISpanExporter. The fixture
    attaches a process_otel_spans method to the client for manual span export.

    Args:
        client: The test client instance.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        Any: The patched client with a process_otel_spans method.
    """
    mock_otlp_exporter = MockOTLPExporter()

    with patch(
        "weave.integrations.pydantic_ai.utils.get_otlp_headers_from_weave_context"
    ) as mock_get_headers:
        mock_get_headers.return_value = {
            "Authorization": "test_auth_token",
            "project_id": "test/test-project",
        }

        original_init = PydanticAISpanExporter.__init__

        def patched_init(self: Any) -> None:
            self._otlp_exporter = mock_otlp_exporter

        monkeypatch.setattr(PydanticAISpanExporter, "__init__", patched_init)

        def process_spans(project_id: Optional[str] = None) -> None:
            """
            Convert and send spans to the server using the mock exporter.

            Args:
                project_id: Optional project ID to use for the export.
            """
            if not project_id:
                project_id = client._project_id()

            # Only process if there are spans to export
            if not mock_otlp_exporter.exported_spans:
                return

            # --- Build OTLP protobuf structures for export ---
            scope = InstrumentationScope()
            scope.name = "pydantic_ai_test"
            scope.version = "1.0.0"

            scope_spans = ScopeSpans()
            scope_spans.scope.CopyFrom(scope)

            for readable_span in mock_otlp_exporter.exported_spans:
                proto_span = convert_readable_span_to_proto_span(readable_span)
                scope_spans.spans.append(proto_span)

            resource = Resource()
            service_kv = KeyValue()
            service_kv.key = "service.name"
            service_kv.value.string_value = "pydantic_ai_test_service"
            resource.attributes.append(service_kv)

            resource_spans = ResourceSpans()
            resource_spans.resource.CopyFrom(resource)
            resource_spans.scope_spans.append(scope_spans)

            request = ExportTraceServiceRequest()
            request.resource_spans.append(resource_spans)

            export_req = tsi.OtelExportReq(
                project_id=project_id, traces=request, wb_user_id=None
            )

            client.server.otel_export(export_req)
            mock_otlp_exporter.exported_spans = []

        client.process_otel_spans = process_spans

        yield client

        monkeypatch.setattr(PydanticAISpanExporter, "__init__", original_init)


@pytest.fixture
def pydantic_ai_client_creator(
    request: Any, monkeypatch: Any
) -> Callable[..., contextlib._GeneratorContextManager[Any]]:
    """
    Fixture that provides a client creator function for pydantic-ai testing.

    This fixture returns a context manager that yields a patched client with a
    mocked PydanticAISpanExporter, allowing for isolated test environments.
    The context manager attaches a process_otel_spans method to the client for
    manual span export.

    Args:
        request: The pytest request fixture.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        Callable[..., contextlib._GeneratorContextManager[Any]]: A context manager
            for creating a patched client.
    """

    @contextlib.contextmanager
    def create_client(
        autopatch_settings: Any = None, global_attributes: Any = None
    ) -> Generator[Any, None, None]:
        """
        Context manager to create a patched client for testing.

        Args:
            autopatch_settings: Optional autopatch settings for the client.
            global_attributes: Optional global attributes for the client.

        Yields:
            Any: The patched client instance.
        """
        from tests.conftest import create_client as original_create_client

        mock_otlp_exporter = MockOTLPExporter()

        with patch(
            "weave.integrations.pydantic_ai.utils.get_otlp_headers_from_weave_context"
        ) as mock_get_headers:
            mock_get_headers.return_value = {
                "Authorization": "test_auth_token",
                "project_id": "test/test-project",
            }

            original_init = PydanticAISpanExporter.__init__

            def patched_init(self: Any) -> None:
                self._otlp_exporter = mock_otlp_exporter

            monkeypatch.setattr(PydanticAISpanExporter, "__init__", patched_init)

            inited_client = original_create_client(
                request, autopatch_settings, global_attributes
            )
            client = inited_client.client

            def process_spans(project_id: Optional[str] = None) -> None:
                """
                Convert and send spans to the server using the mock exporter.

                Args:
                    project_id: Optional project ID to use for the export.
                """
                if not project_id:
                    project_id = client._project_id()

                # Only process if there are spans to export
                if not mock_otlp_exporter.exported_spans:
                    return

                # --- Build OTLP protobuf structures for export ---
                scope = InstrumentationScope()
                scope.name = "pydantic_ai_test"
                scope.version = "1.0.0"

                scope_spans = ScopeSpans()
                scope_spans.scope.CopyFrom(scope)

                for readable_span in mock_otlp_exporter.exported_spans:
                    proto_span = convert_readable_span_to_proto_span(readable_span)
                    scope_spans.spans.append(proto_span)

                resource = Resource()
                service_kv = KeyValue()
                service_kv.key = "service.name"
                service_kv.value.string_value = "pydantic_ai_test_service"
                resource.attributes.append(service_kv)

                resource_spans = ResourceSpans()
                resource_spans.resource.CopyFrom(resource)
                resource_spans.scope_spans.append(scope_spans)

                request = ExportTraceServiceRequest()
                request.resource_spans.append(resource_spans)

                export_req = tsi.OtelExportReq(
                    project_id=project_id, traces=request, wb_user_id=None
                )

                client.server.otel_export(export_req)
                mock_otlp_exporter.exported_spans = []

            client.process_otel_spans = process_spans

            try:
                yield client
            finally:
                inited_client.reset()
                monkeypatch.setattr(PydanticAISpanExporter, "__init__", original_init)

    return create_client
