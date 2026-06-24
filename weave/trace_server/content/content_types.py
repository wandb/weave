from pathlib import Path
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field
from typing_extensions import NotRequired

DataUrlContentType = Literal[
    "data_url", "data_url:base64", "data_url:encoding", "data_url:encoding:base64"
]

ContentType = Literal["bytes", "text", "base64", "file", "url", DataUrlContentType]

ValidContentInputs = bytes | str | Path


# This is what is saved to the 'metadata.json' file by serialization layer
# It is used to 'restore' an existing content object
class ResolvedContentArgsWithoutData(TypedDict):
    # Required Fields
    size: int
    mimetype: str
    digest: str
    filename: str
    content_type: ContentType
    input_type: str
    encoding: str

    # Optional fields - can be omitted
    metadata: NotRequired[dict[str, Any]]
    extension: NotRequired[str]


class ResolvedContentArgs(ResolvedContentArgsWithoutData):
    # Required Fields
    data: bytes


class DataUrlParamsBase(BaseModel):
    mimetype: str
    data: bytes
    encoding: str = "us-ascii"


class DataUrlSimple(DataUrlParamsBase):
    content_type: Literal["data_url"]


class DataUrlBase64(DataUrlParamsBase):
    content_type: Literal["data_url:base64"]


class DataUrlWithEncoding(DataUrlParamsBase):
    content_type: Literal["data_url:encoding"]


class DataUrlBase64WithEncoding(DataUrlParamsBase):
    content_type: Literal["data_url:encoding:base64"]


class DataUrl(BaseModel):
    params: (
        DataUrlSimple | DataUrlBase64 | DataUrlWithEncoding | DataUrlBase64WithEncoding
    ) = Field(discriminator="content_type")
