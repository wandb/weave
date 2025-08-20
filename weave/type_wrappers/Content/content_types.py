from pathlib import Path
from typing import Any, Literal, TypedDict, Union

from typing_extensions import NotRequired

ContentType = Literal["bytes", "text", "base64", "file"]

ValidContentInputs = Union[bytes, str, Path]


# This is what is saved to the 'metadata.json' file by serialization layer
# It is used to 'restore' an existing content object
class ResolvedContentArgsWithoutData(TypedDict):
    # Required Fields
    id: str
    size: int
    mimetype: str
    digest: str
    filename: str
    content_type: ContentType
    input_type: str
    encoding: str

    # Optional fields - can be omitted
    metadata: NotRequired[dict[str, Any]]
    path: NotRequired[str]
    extension: NotRequired[str]


class ResolvedContentArgs(ResolvedContentArgsWithoutData):
    # Required Fields
    data: bytes
