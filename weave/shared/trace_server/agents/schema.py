from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

SpanKindLiteral = Literal[
    "UNSPECIFIED",
    "INTERNAL",
    "SERVER",
    "CLIENT",
    "PRODUCER",
    "CONSUMER",
]
StatusCodeLiteral = Literal["UNSET", "OK", "ERROR"]

# Operation names of agent spans the server emits scoring events for. This is a
# server/wire concept (the span op-name the server produces and matches on), so
# the trace server owns it here. `weave.flow.monitor` keeps an independent copy
# of the same literal for the client-side `Monitor.op_names` field; the two are
# deliberately not shared, to keep the trace server free of client imports.
AgentSpanOpName: TypeAlias = Literal["weave.genai.turn_ended"]
# Empty string means the provider did not specify an output modality; it
# mirrors the ClickHouse string-column default for newly inserted spans.
OutputTypeLiteral = Literal["", "text", "json", "image", "speech"]


class NormalizedMessage(BaseModel):
    """A single message normalized from any provider format.

    Maps to ClickHouse ``Tuple(role String, content String, finish_reason String)``.

    - role: message role (user, assistant, tool, system)
    - content: plain text for simple messages, or JSON-serialized parts
      array for multimodal/structured messages
    - finish_reason: per-message finish reason (output messages only)

    Serialization JSON Schema marks defaulted fields required. In the public
    OpenAPI document this class appears only as an AgentSpanSchema message
    element. Ingest validation is unchanged.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    role: str = ""
    content: str
    finish_reason: str = ""
