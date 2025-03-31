"""Type stub for the python_spans module."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Union, Tuple
from weave.trace_server import trace_server_interface as tsi
import datetime

from opentelemetry.proto.common.v1.common_pb2 import (
   KeyValue, InstrumentationScope
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    TracesData as PbTracesData,
    ResourceSpans as PbResourceSpans,
    ScopeSpans as PbScopeSpans,
    Span as PbSpan,
    Status as PbStatus,
)

class SpanKind(Enum):
    UNSPECIFIED: int
    INTERNAL: int
    SERVER: int
    CLIENT: int
    PRODUCER: int
    CONSUMER: int

    @classmethod
    def from_proto(cls, proto_kind: int) -> 'SpanKind': ...

class StatusCode(Enum):
    UNSET: int
    OK: int
    ERROR: int

    @classmethod
    def from_proto(cls, proto_code: int) -> 'StatusCode': ...

@dataclass
class Status:
    code: StatusCode
    message: str

    @classmethod
    def from_proto(cls, proto_status: PbStatus) -> 'Status': ...

@dataclass
class Event:
    name: str
    timestamp: int  # nanoseconds since epoch
    attributes: List[KeyValue]
    dropped_attributes_count: int

    @property
    def datetime(self) -> datetime.datetime: ...

    @classmethod
    def from_proto(cls, proto_event: PbSpan.Event) -> 'Event': ...

@dataclass
class Link:
    trace_id: str
    span_id: str
    trace_state: str
    attributes: List[KeyValue]
    dropped_attributes_count: int
    flags: int

    @classmethod
    def from_proto(cls, proto_link: PbSpan.Link) -> 'Link': ...

@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    kind: SpanKind
    parent_span_id: str
    trace_state: str
    flags: int
    attributes: List[KeyValue]
    dropped_attributes_count: int
    events: List[Event]
    dropped_events_count: int
    links: List[Link]
    dropped_links_count: int
    status: Status

    @property
    def start_time(self) -> datetime.datetime: ...

    @property
    def end_time(self) -> datetime.datetime: ...

    @property
    def duration_ns(self) -> int: ...

    @property
    def duration_ms(self) -> float: ...

    @classmethod
    def from_proto(cls, proto_span: PbSpan) -> 'Span': ...

    def to_call(self, project_id: str) -> Tuple[tsi.StartedCallSchemaForInsert, tsi.EndedCallSchemaForInsert]: ...

@dataclass
class ScopeSpans:
    scope: InstrumentationScope
    spans: List[Span]
    schema_url: str

    @classmethod
    def from_proto(cls, proto_scope_spans: PbScopeSpans) -> 'ScopeSpans': ...

@dataclass
class ResourceSpans:
    resource: Resource
    scope_spans: List[ScopeSpans]
    schema_url: str

    @classmethod
    def from_proto(cls, proto_resource_spans: PbResourceSpans) -> 'ResourceSpans': ...

@dataclass
class TracesData:
    resource_spans: List[ResourceSpans]

    @classmethod
    def from_proto(cls, proto_traces_data: PbTracesData) -> 'TracesData': ...

def create_span(
    name: str,
    trace_id: Union[str, bytes],
    span_id: Union[str, bytes],
    start_time: Union[int, datetime.datetime],
    end_time: Union[int, datetime.datetime],
    kind: SpanKind = ...,
    parent_span_id: Optional[Union[str, bytes]] = ...,
    attributes: Optional[Dict] = ...,
    status: Optional[Status] = ...,
) -> Span: ...
