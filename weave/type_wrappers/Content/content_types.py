from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, TypedDict, Union

from pydantic import Field

MetadataKeysType = str | int
MetadataValueType = MetadataKeysType | list["MetadataValueType"] | dict[MetadataKeysType, "MetadataValueType"]
MetadataType = dict[MetadataKeysType, "MetadataValueType"]

ContentType = Literal['bytes', 'text', 'base64', 'file', 'url']

ValidContentInputs =  bytes | str | Path

# These represent the args the user can pass in to create various types of content
# Optional args that can be passed to any content
class BaseContentArgs(TypedDict):
    mimetype: str | None
    metadata: MetadataType | None

class BytesContentArgs(BaseContentArgs):
    data: bytes
    encoding: str | None
    content_type: Literal['bytes']

class TextContentArgs(BaseContentArgs):
    text: str
    encoding: str | None
    content_type: Literal['text']

class FileContentArgs(BaseContentArgs):
    path: str | Path
    encoding: str | None
    content_type: Literal['file']

class Base64ContentArgs(BaseContentArgs):
    b64_data: str | bytes
    content_type: Literal['base64']

class UrlContentArgs(BaseContentArgs):
    url: str
    headers: dict
    content_type: Literal['url']

ContentArgs = Annotated[
    Union[
        BytesContentArgs,
        TextContentArgs,
        FileContentArgs,
        Base64ContentArgs,
        UrlContentArgs
    ],
    Field(discriminator='content_type')
]

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
    extra: MetadataType

    # Optional Fields
    path: str | None
    extension: str | None
    encoding: str | None

class ResolvedContentArgs(ResolvedContentArgsWithoutData):
    # Required Fields
    data: bytes
