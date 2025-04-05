"""Human-readable wrapper classes for OpenTelemetry trace protocol buffer definitions.

This module provides simple, human-readable Python classes that represent the
trace protocol buffer definitions from opentelemetry.proto.trace.v1.trace_pb2.
"""

import datetime
from binascii import hexlify
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from opentelemetry.proto.common.v1.common_pb2 import (
    AnyValue,
    InstrumentationScope,
    KeyValue,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans as PbResourceSpans,
)
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ScopeSpans as PbScopeSpans,
)
from opentelemetry.proto.trace.v1.trace_pb2 import (
    Span as PbSpan,
)
from opentelemetry.proto.trace.v1.trace_pb2 import (
    Status as PbStatus,
)
from opentelemetry.proto.trace.v1.trace_pb2 import (
    TracesData as PbTracesData,
)
from typing_extensions import assert_never

from weave.trace_server import trace_server_interface as tsi

from .attributes import (
    Attributes,
    AttributesFactory,
    to_json_serializable,
)


class SpanKind(Enum):
    """Enum representing the span's kind."""

    UNSPECIFIED = 0
    INTERNAL = 1
    SERVER = 2
    CLIENT = 3
    PRODUCER = 4
    CONSUMER = 5

    @classmethod
    def from_proto(cls, proto_kind: int) -> "SpanKind":
        """Convert from protobuf enum value to SpanKind."""
        return cls(proto_kind)


class StatusCode(Enum):
    """Enum representing the span's status code."""

    UNSET = 0
    OK = 1
    ERROR = 2

    @classmethod
    def from_proto(cls, proto_code: int) -> "StatusCode":
        """Convert from protobuf enum value to StatusCode."""
        return cls(proto_code)


@dataclass
class Status:
    """Represents the status of a span."""

    code: StatusCode = StatusCode.UNSET
    message: str = ""

    @classmethod
    def from_proto(cls, proto_status: PbStatus) -> "Status":
        """Create a Status from a protobuf Status."""
        return cls(
            code=StatusCode.from_proto(proto_status.code), message=proto_status.message
        )

    def to_weave_status(self) -> Optional[tsi.TraceStatus]:
        """Convert from protobuf enum value to StatusCode."""
        if self.code == StatusCode.OK:
            return tsi.TraceStatus.SUCCESS
        elif self.code == StatusCode.ERROR:
            return tsi.TraceStatus.ERROR
        # UNSET: This is not 'running' because if the trace was sent the call completed
        return None


@dataclass
class Event:
    """Represents a timed event in a span."""

    name: str
    timestamp: int  # nanoseconds since epoch
    attributes: list[KeyValue] = field(default_factory=list)
    dropped_attributes_count: int = 0

    @property
    def datetime(self) -> datetime.datetime:
        """Return the timestamp as a datetime object."""
        return datetime.datetime.fromtimestamp(self.timestamp / 1_000_000_000)

    @classmethod
    def from_proto(cls, proto_event: PbSpan.Event) -> "Event":
        """Create an Event from a protobuf Event."""
        return cls(
            name=proto_event.name,
            timestamp=proto_event.time_unix_nano,
            attributes=list(proto_event.attributes),
            dropped_attributes_count=proto_event.dropped_attributes_count,
        )


@dataclass
class Link:
    """Represents a link to another span."""

    trace_id: str
    span_id: str
    trace_state: str = ""
    attributes: list[KeyValue] = field(default_factory=list)
    dropped_attributes_count: int = 0
    flags: int = 0

    @classmethod
    def from_proto(cls, proto_link: PbSpan.Link) -> "Link":
        """Create a Link from a protobuf Link."""
        return cls(
            trace_id=hexlify(proto_link.trace_id).decode("ascii"),
            span_id=hexlify(proto_link.span_id).decode("ascii"),
            trace_state=proto_link.trace_state,
            attributes=list(proto_link.attributes),
            dropped_attributes_count=proto_link.dropped_attributes_count,
            flags=proto_link.flags,
        )


def _decode_key_values(
    key_values: Iterable[KeyValue],
) -> Iterator[tuple[str, Any]]:
    return ((kv.key, _decode_value(kv.value)) for kv in key_values)


def _decode_value(any_value: AnyValue) -> Any:
    which = any_value.WhichOneof("value")
    if which == "string_value":
        return any_value.string_value
    if which == "bool_value":
        return any_value.bool_value
    if which == "int_value":
        return any_value.int_value
    if which == "double_value":
        return any_value.double_value
    if which == "array_value":
        return [_decode_value(value) for value in any_value.array_value.values]
    if which == "kvlist_value":
        return dict(_decode_key_values(any_value.kvlist_value.values))
    if which == "bytes_value":
        return any_value.bytes_value
    if which is None:
        return None
    assert_never(which)


@dataclass
class Span:
    """Represents a span in a trace."""

    name: str
    trace_id: str
    span_id: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: Attributes
    kind: SpanKind = SpanKind.UNSPECIFIED
    parent_id: Optional[str] = None
    trace_state: str = ""
    flags: int = 0
    dropped_attributes_count: int = 0
    events: list[Event] = field(default_factory=list)
    dropped_events_count: int = 0
    links: list[Link] = field(default_factory=list)
    dropped_links_count: int = 0
    status: Status = field(default_factory=Status)

    @property
    def start_time(self) -> datetime.datetime:
        """Return the start time as a datetime object."""
        return datetime.datetime.fromtimestamp(
            self.start_time_unix_nano / 1_000_000_000
        )

    @property
    def end_time(self) -> datetime.datetime:
        """Return the end time as a datetime object."""
        return datetime.datetime.fromtimestamp(self.end_time_unix_nano / 1_000_000_000)

    @property
    def duration_ns(self) -> int:
        """Return the duration in nanoseconds."""
        return self.end_time_unix_nano - self.start_time_unix_nano

    @property
    def duration_ms(self) -> float:
        """Return the duration in milliseconds."""
        return self.duration_ns / 1_000_000

    @classmethod
    def from_proto(cls, proto_span: PbSpan) -> "Span":
        """Create a Span from a protobuf Span."""
        parent_id = None
        if proto_span.parent_span_id:
            parent_id = hexlify(proto_span.parent_span_id).decode("ascii")

        return cls(
            name=proto_span.name,
            trace_id=hexlify(proto_span.trace_id).decode("ascii"),
            span_id=hexlify(proto_span.span_id).decode("ascii"),
            start_time_unix_nano=proto_span.start_time_unix_nano,
            end_time_unix_nano=proto_span.end_time_unix_nano,
            kind=SpanKind.from_proto(proto_span.kind),
            parent_id=parent_id,
            trace_state=proto_span.trace_state,
            flags=proto_span.flags,
            attributes=AttributesFactory().from_proto(key_values=proto_span.attributes),
            dropped_attributes_count=proto_span.dropped_attributes_count,
            events=[Event.from_proto(e) for e in proto_span.events],
            dropped_events_count=proto_span.dropped_events_count,
            links=[Link.from_proto(l) for l in proto_span.links],
            dropped_links_count=proto_span.dropped_links_count,
            status=Status.from_proto(proto_span.status),
        )

    def to_call(
        self, project_id: str
    ) -> tuple[tsi.StartedCallSchemaForInsert, tsi.EndedCallSchemaForInsert]:
        print("before summary")
        summary_insert_map = tsi.SummaryInsertMap(
            usage={"usage": self.attributes.extract_usage()}
        )
        print("after summary")
        inputs = to_json_serializable(self.attributes.extract_inputs())
        print("after inputs")
        outputs = to_json_serializable(self.attributes.extract_outputs())
        print("after outputs")
        attributes = to_json_serializable(self.attributes.extract_attributes())
        print("after attributes")

        # Options: set
        start_call = tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=self.span_id,
            op_name=self.name,
            trace_id=self.trace_id,
            parent_id=self.parent_id,
            started_at=self.start_time,
            attributes=attributes,
            inputs=inputs,
            wb_user_id=None,
            wb_run_id=None,
        )
        print("after start_call")
        exception_msg = (
            self.status.message if self.status.code == StatusCode.ERROR else None
        )

        print("after end_call")
        end_call = tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=self.span_id,
            ended_at=self.end_time,
            exception=exception_msg,
            output=outputs,
            summary=summary_insert_map,
        )
        return (start_call, end_call)


@dataclass
class ScopeSpans:
    """Represents a collection of spans from a specific instrumentation scope."""

    scope: InstrumentationScope
    spans: list[Span] = field(default_factory=list)
    schema_url: str = ""

    def __iter__(self) -> Iterator[Span]:
        yield from self.spans

    @classmethod
    def from_proto(cls, proto_scope_spans: PbScopeSpans) -> "ScopeSpans":
        """Create a ScopeSpans from a protobuf ScopeSpans."""
        return cls(
            scope=proto_scope_spans.scope,
            spans=[Span.from_proto(s) for s in proto_scope_spans.spans],
            schema_url=proto_scope_spans.schema_url,
        )


@dataclass
class ResourceSpans:
    """Represents a collection of spans from a specific resource."""

    resource: Optional[Resource]
    scope_spans: list[ScopeSpans] = field(default_factory=list)
    schema_url: str = ""

    def __iter__(self) -> Iterator[ScopeSpans]:
        yield from self.scope_spans

    @classmethod
    def from_proto(cls, proto_resource_spans: PbResourceSpans) -> "ResourceSpans":
        """Create a ResourceSpans from a protobuf ResourceSpans."""
        return cls(
            resource=proto_resource_spans.resource,
            scope_spans=[
                ScopeSpans.from_proto(s) for s in proto_resource_spans.scope_spans
            ],
            schema_url=proto_resource_spans.schema_url,
        )


@dataclass
class TracesData:
    """Top-level collection of trace data."""

    resource_spans: list[ResourceSpans] = field(default_factory=list)

    def __iter__(self) -> Iterator[ResourceSpans]:
        yield from self.resource_spans

    @classmethod
    def from_proto(cls, proto_traces_data: PbTracesData) -> "TracesData":
        """Create a TracesData from a protobuf TracesData."""
        return cls(
            resource_spans=[
                ResourceSpans.from_proto(rs) for rs in proto_traces_data.resource_spans
            ]
        )
