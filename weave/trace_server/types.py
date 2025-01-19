from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

if TYPE_CHECKING:
    from weave.trace_server.trace_server_interface import CallSchema

JsonDict = Annotated[
    dict[str, Any],
    Field(json_schema_extra={"additionalProperties": True}),
]

StreamingCalls = Annotated[
    Iterator["CallSchema"],
    Field(
        json_schema_extra={
            "type": "array",
            "items": {"$ref": "#/components/schemas/CallSchema"},
        }
    ),
]
