from pydantic import AfterValidator
from typing_extensions import Annotated

from weave.errors import WeaveInvalidStringError

INVALID_BACKEND_STRING_CHARS = {":", " ", "/"}


def valid_backend_string(v: str) -> str:
    for c in INVALID_BACKEND_STRING_CHARS:
        if c in v:
            raise WeaveInvalidStringError(f"Invalid string: {v} (contains `{c}`)")
    return v


BackendString = Annotated[str, AfterValidator(valid_backend_string)]
