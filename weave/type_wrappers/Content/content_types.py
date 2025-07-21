from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

MetadataKeysType = str | int
MetadataValueType = (
    MetadataKeysType
    | list["MetadataValueType"]
    | dict[MetadataKeysType, "MetadataValueType"]
)
MetadataType = dict[MetadataKeysType, "MetadataValueType"]

ContentType = Literal["bytes", "text", "base64", "file", "url"]

ValidContentInputs = bytes | str | Path


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

    # Optional Fields
    extra: MetadataType | None
    path: str | None
    extension: str | None
    encoding: str | None


class ResolvedContentArgs(ResolvedContentArgsWithoutData):
    # Required Fields
    data: bytes
