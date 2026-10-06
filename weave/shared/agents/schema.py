"""Span and message shapes shared by the agent API models and the spans table."""

from typing import Literal

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
