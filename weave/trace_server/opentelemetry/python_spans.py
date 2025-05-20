"""Human-readable wrapper classes for OpenTelemetry trace protocol buffer definitions.

This module provides simple, human-readable Python classes that represent the
trace protocol buffer definitions from opentelemetry.proto.trace.v1.trace_pb2.
"""

import datetime
import hashlib
from binascii import hexlify
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
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

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH, MAX_OP_NAME_LENGTH
from weave.trace_server.opentelemetry.attributes import (
    SpanEvent,
    get_span_overrides,
    get_wandb_attributes,
    get_weave_attributes,
    get_weave_inputs,
    get_weave_outputs,
    get_weave_usage,
)
from weave.trace_server.opentelemetry.helpers import (
    shorten_name,
    to_json_serializable,
    unflatten_key_values,
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

    def as_weave_status(self) -> Optional[tsi.TraceStatus]:
        """Convert from protobuf enum value to StatusCode."""
        if self.code == StatusCode.OK:
            return tsi.TraceStatus.SUCCESS
        elif self.code == StatusCode.ERROR:
            return tsi.TraceStatus.ERROR
        # UNSET: This is not 'running' because if the trace was sent the call completed
        return None

    def as_dict(self) -> dict[str, Any]:
        return to_json_serializable(
            {
                "code": self.code.name,
                "message": self.message,
            }
        )


@dataclass
class Event:
    """Represents a timed event in a span."""

    name: str
    timestamp: int  # nanoseconds since epoch
    attributes: dict[str, Any] = field(default_factory=dict)
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
            attributes=unflatten_key_values(proto_event.attributes),
            dropped_attributes_count=proto_event.dropped_attributes_count,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.datetime,
            "attributes": self.attributes,
            "dropped_attributes_count": self.dropped_attributes_count,
        }


@dataclass
class Link:
    """Represents a link to another span."""

    trace_id: str
    span_id: str
    trace_state: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    dropped_attributes_count: int = 0
    flags: int = 0

    @classmethod
    def from_proto(cls, proto_link: PbSpan.Link) -> "Link":
        """Create a Link from a protobuf Link."""
        return cls(
            trace_id=hexlify(proto_link.trace_id).decode("ascii"),
            span_id=hexlify(proto_link.span_id).decode("ascii"),
            trace_state=proto_link.trace_state,
            attributes=unflatten_key_values(proto_link.attributes),
            dropped_attributes_count=proto_link.dropped_attributes_count,
            flags=proto_link.flags,
        )


@dataclass
class Resource:
    attributes: dict[str, Any] = field(default_factory=dict)
    dropped_attributes_count: int = 0

    @classmethod
    def from_proto(cls, proto_resource: PbResource) -> "Resource":
        attributes = {}
        if proto_resource.attributes:
            attributes = unflatten_key_values(proto_resource.attributes)
        dropped_attributes_count = 0
        if proto_resource.dropped_attributes_count:
            dropped_attributes_count = proto_resource.dropped_attributes_count
        return cls(attributes, dropped_attributes_count)

    def as_dict(self) -> dict[str, Any]:
        return {
            "attributes": self.attributes,
            "dropped_attributes_count": self.dropped_attributes_count,
        }


@dataclass
class Span:
    """Represents a span in a trace."""

    resource: Optional[Resource]
    name: str
    trace_id: str
    span_id: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: dict[str, Any] = field(default_factory=dict)
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
    def from_proto(
        cls, proto_span: PbSpan, resource: Optional[Resource] = None
    ) -> "Span":
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
            attributes=unflatten_key_values(proto_span.attributes),
            dropped_attributes_count=proto_span.dropped_attributes_count,
            events=[Event.from_proto(e) for e in proto_span.events],
            dropped_events_count=proto_span.dropped_events_count,
            links=[Link.from_proto(l) for l in proto_span.links],
            dropped_links_count=proto_span.dropped_links_count,
            status=Status.from_proto(proto_span.status),
            resource=resource,
        )

    # The full OTEL Span as it is recieved
    def as_dict(self) -> dict[str, Any]:
        return to_json_serializable(
            {
                "name": self.name,
                "context": {
                    "trace_id": self.trace_id,
                    "span_id": self.span_id,
                    "trace_state": self.trace_state,
                },
                "kind": self.kind.name,
                "parent_id": self.parent_id,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "status": self.status.as_dict(),
                "attributes": self.attributes,
                "events": self.events,
                "links": self.links,
                "resource": self.resource.as_dict() if self.resource else None,
            }
        )

    def to_call(
        self, project_id: str
    ) -> tuple[tsi.StartedCallSchemaForInsert, tsi.EndedCallSchemaForInsert]:
        events = [SpanEvent(e.as_dict()) for e in self.events]
        usage = get_weave_usage(self.attributes) or {}
        inputs = get_weave_inputs(events, self.attributes) or {}
        outputs = get_weave_outputs(events, self.attributes) or {}
        attributes = get_weave_attributes(self.attributes) or {}
        wandb_attributes = get_wandb_attributes(self.attributes) or {}
        overrides = get_span_overrides(self.attributes) or {}

        start_time = overrides.get("start_time") or self.start_time
        end_time = overrides.get("end_time") or self.end_time

        llm_usage = tsi.LLMUsageSchema(
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            prompt_tokens=usage.get("prompt_tokens"),
            total_tokens=usage.get("total_tokens"),
            requests=usage.get("requests"),
        )

        # Read the model name from attributes to load cost info
        model = attributes.get("model")
        if not model:
            model_parameters = attributes.get("model_parameters")
            if model_parameters:
                model = model_parameters.get("model")

        usage_key = model or "usage"
        summary_insert_map = tsi.SummaryInsertMap(usage={usage_key: llm_usage})

        has_attributes = len(attributes) > 0
        has_inputs = len(inputs) > 0
        has_outputs = len(outputs) > 0
        has_usage = len(usage) > 0

        # We failed to load any of the Weave attributes, dump all attributes
        if not has_attributes and not has_inputs and not has_outputs and not has_usage:
            attributes = to_json_serializable(self.attributes)

        attributes["otel_span"] = self.as_dict()
        op_name = self.name

        display_name = wandb_attributes.get("display_name")
        if display_name and len(display_name) >= MAX_DISPLAY_NAME_LENGTH:
            display_name = shorten_name(display_name, MAX_DISPLAY_NAME_LENGTH)

        if len(op_name) >= MAX_OP_NAME_LENGTH:
            # Since op_name will typically be what is displayed, we don't want to just truncate
            # Create an identifier abbreviation so similar long names can be distinguished
            identifier = hashlib.sha256(op_name.encode("utf-8")).hexdigest()[:4]
            op_name = shorten_name(
                op_name,
                MAX_OP_NAME_LENGTH,
                abbrv=f":{identifier}",
                use_delimiter_in_abbr=False,
            )

        start_call = tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=self.span_id,
            op_name=op_name,
            trace_id=self.trace_id,
            parent_id=self.parent_id,
            started_at=start_time,
            attributes=attributes,
            inputs=inputs,
            display_name=display_name,
            wb_user_id=None,
            wb_run_id=None,
        )
        exception_msg = (
            self.status.message if self.status.code == StatusCode.ERROR else None
        )

        end_call = tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=self.span_id,
            ended_at=end_time,
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
    def from_proto(
        cls, proto_scope_spans: PbScopeSpans, resource: Optional[Resource] = None
    ) -> "ScopeSpans":
        """Create a ScopeSpans from a protobuf ScopeSpans."""
        return cls(
            scope=proto_scope_spans.scope,
            spans=[Span.from_proto(s, resource) for s in proto_scope_spans.spans],
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
        resource = Resource.from_proto(proto_resource_spans.resource)
        return cls(
            resource=resource,
            scope_spans=[
                ScopeSpans.from_proto(s, resource)
                for s in proto_resource_spans.scope_spans
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
