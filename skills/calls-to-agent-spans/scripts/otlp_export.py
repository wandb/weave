"""Encode spans as OTLP and post them to the agents ingest endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import requests
from calls_client import TIMEOUT
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
    Status,
)


def to_otlp(spans: list[dict[str, object]]) -> ExportTraceServiceRequest:
    """Wrap the spans in one OTLP export request."""
    proto_spans = []
    for span in spans:
        proto = Span(
            trace_id=_trace_bytes(span["trace_id"]),
            span_id=_span_bytes(span["span_id"]),
            parent_span_id=_span_bytes(span["parent_span_id"]),
            name=span["name"],
            kind=SPAN_KINDS[span["kind"]],
            start_time_unix_nano=_nanos(span["started_at"]),
            end_time_unix_nano=_nanos(span["ended_at"]),
            status=Status(code=Status.STATUS_CODE_ERROR)
            if span["error"]
            else Status(code=Status.STATUS_CODE_UNSET),
        )
        for key, value in span["attributes"].items():
            proto.attributes.append(KeyValue(key=key, value=_any_value(value)))
        proto_spans.append(proto)
    return ExportTraceServiceRequest(
        resource_spans=[ResourceSpans(scope_spans=[ScopeSpans(spans=proto_spans)])]
    )


def export_spans(
    session: requests.Session,
    base_url: str,
    project: str,
    request: ExportTraceServiceRequest,
) -> None:
    """POST one OTLP batch. The endpoint accepts protobuf only; JSON is rejected."""
    response = session.post(
        f"{base_url}/agents/otel/v1/traces",
        data=request.SerializeToString(),
        headers={"Content-Type": "application/x-protobuf", "project_id": project},
        timeout=TIMEOUT,
    )
    response.raise_for_status()


def _trace_bytes(value: str) -> bytes:
    """A classic trace id is a uuid, which is exactly the 16 bytes OTLP wants."""
    try:
        return uuid.UUID(value).bytes
    except ValueError:
        return value.encode()[:16].ljust(16, b"\0")


def _span_bytes(value: str) -> bytes:
    """OTLP span ids are 8 bytes, so a 16-byte call id keeps its first half."""
    if not value:
        return b""
    return _trace_bytes(value)[:8]


def _nanos(timestamp: str) -> int:
    if not timestamp:
        return 0
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1_000_000_000)


def _any_value(value: object) -> AnyValue:
    if isinstance(value, bool):
        return AnyValue(bool_value=value)
    if isinstance(value, int):
        return AnyValue(int_value=value)
    if isinstance(value, float):
        return AnyValue(double_value=value)
    return AnyValue(string_value=str(value))


EXPORT_BATCH = 500
SPAN_KINDS = {"CLIENT": Span.SPAN_KIND_CLIENT, "INTERNAL": Span.SPAN_KIND_INTERNAL}
