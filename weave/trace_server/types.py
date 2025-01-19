from typing import Annotated, Any

from pydantic import Field

JsonDict = Annotated[
    dict[str, Any],
    Field(json_schema_extra={"additionalProperties": True}),
]
