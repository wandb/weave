from pydantic import BaseModel, Field

from weave.trace_server.trace_server_interface import (
    EndedCallSchemaForInsert,
    StartedCallSchemaForInsert,
)


class CallPair(BaseModel):
    start: StartedCallSchemaForInsert
    end: EndedCallSchemaForInsert


class RejectedOTelSpan(BaseModel):
    error: str
    name: str = ""
    trace_id: str = ""
    span_id: str = ""


class OTelSpanParseResult(BaseModel):
    calls: list[CallPair] = Field(default_factory=list)
    rejected: list[RejectedOTelSpan] = Field(default_factory=list)
