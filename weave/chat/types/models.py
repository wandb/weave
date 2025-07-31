# For simplicity now, just doing this instead of bringing over SyncPage stuff from OpenAI.

from collections.abc import Iterator
from typing import Literal, Union

from weave.chat.types._models import BaseModel
from weave.chat.types.model import Model


class ModelsResponseSuccess(BaseModel):
    object: Literal["list"]
    """The object type, which is always "list"."""

    data: list[Model]

    def __iter__(self) -> Iterator[Model]:
        return iter(self.data)


class ModelsResponseErrorDetails(BaseModel):
    """Error details from the API response."""

    code: str
    """The error code."""

    message: str
    """The error message."""

    type: str
    """The error type."""


class ModelsResponseError(BaseModel):
    error: ModelsResponseErrorDetails


ModelsResponse = Union[ModelsResponseSuccess, ModelsResponseError]
