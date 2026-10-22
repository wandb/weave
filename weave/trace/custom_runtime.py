"""The runtime ID type that `WeaveClient.register_custom_runtime` takes."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from weave.trace.constants import DEFAULT_CUSTOM_RUNTIME_MAX_TOKENS


class CustomRuntimeID(BaseModel):
    id: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            # Forbid whitespace.
            pattern=r"^\S+$",
        ),
    ] = Field(description="Value sent in the OpenAI-compatible request model field")
    max_tokens: int = Field(
        default=DEFAULT_CUSTOM_RUNTIME_MAX_TOKENS,
        gt=0,
        description="Maximum tokens supported by this runtime ID",
    )
