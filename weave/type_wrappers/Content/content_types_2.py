from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, TypedDict, Union

from pydantic import Field

MetadataKeysType = str | int
MetadataValueType = MetadataKeysType | list["MetadataValueType"] | dict[MetadataKeysType, "MetadataValueType"]
MetadataType = dict[MetadataKeysType, "MetadataValueType"]

ContentType = Literal['bytes', 'text', 'base64', 'file', 'url']


# These represent the args the user can pass in to create various types of content
# Optional args that can be passed to any content
class BaseContentArgs(TypedDict):
    mimetype: str | None
    extension: str | None
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
