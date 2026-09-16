# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import TYPE_CHECKING, Dict, Optional

from pydantic import Field as FieldInfo

from .._models import BaseModel

__all__ = ["CompletionCreateStreamResponse", "_Meta"]


class _Meta(BaseModel):
    """Identifiers of the call the stream is recorded into."""

    conversation_id: Optional[str] = None

    span_id: Optional[str] = None

    trace_id: Optional[str] = None

    weave_call_id: Optional[str] = None


class CompletionCreateStreamResponse(BaseModel):
    """One NDJSON line of the completions stream.

    A tracked call opens with the identifiers, a failure produces `error`, and
    every other line is a provider chunk passed through as it arrived, which is
    why anything else is allowed.
    """

    api_meta: Optional[_Meta] = FieldInfo(alias="_meta", default=None)
    """Identifiers of the call the stream is recorded into."""

    error: Optional[str] = None

    if TYPE_CHECKING:
        # Some versions of Pydantic <2.8.0 have a bug and don’t allow assigning a
        # value to this field, so for compatibility we avoid doing it at runtime.
        __pydantic_extra__: Dict[str, object] = FieldInfo(init=False)  # pyright: ignore[reportIncompatibleVariableOverride]

        # Stub to indicate that arbitrary properties are accepted.
        # To access properties that are not valid identifiers you can use `getattr`, e.g.
        # `getattr(obj, '$type')`
        def __getattr__(self, attr: str) -> object: ...
    else:
        __pydantic_extra__: Dict[str, object]
