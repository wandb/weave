from __future__ import annotations

import base64
import hashlib
import uuid
from pathlib import Path
from typing import Annotated, Generic, Type, TypeVar, TypedDict
# NotRequired is the modern way to specify optional keys in a TypedDict
from typing import NotRequired
from typing_extensions import Unpack

from pydantic import Field, BaseModel

# Assuming utils.py and content_types.py are in the same directory
# and contain the code provided in the problem description.
from utils import (
    get_mime_and_extension,
    default_filename,
    is_valid_path,
)
from content_types import (
    ContentType,
    MetadataType,
    # The original ...ContentArgs are used to name the input_type
    ResolvedContentArgs,
)


class BaseContentHandler(BaseModel):
    id: str
    data: bytes
    size: int
    mimetype: str
    digest: str
    filename: str
    content_type: ContentType
    input_type: str

    extra: Annotated[MetadataType, Field(
        description="Extra metadata to associate with the content",
        examples=[{"number of cats": 1}]
    )] = {}
    encoding: str | None = "utf-8"
    path: str | None = None
    extension: str | None = None

T = TypeVar("T", bound=str)

class Content(Generic[T], BaseContentHandler):
    """
    A class to represent content from various sources, resolving them
    to a unified byte-oriented representation with associated metadata.

    This class provides several factory class methods to handle different
    input types and normalize them into a consistent `Content` object.
    """

    @classmethod
    def from_bytes(
        cls: Type["Content"],
        data: bytes,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: MetadataType = {},
        encoding: str = "utf-8",
    ) -> "Content":
        """Initializes Content from raw bytes."""
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)
        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype,
            extension=extension,
            filename=None,
            buffer=data
        )
        filename = default_filename(extension or "")

        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": 'bytes',
            "input_type": str(type(data)),
            "extra": metadata or {},
            "path": None,
            "extension": extension,
            "encoding": encoding or "utf-8",
        }
        return cls(**resolved_args)

    @classmethod
    def from_text(
        cls: Type["Content"],
        text: str,
        /
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: MetadataType = {},
        encoding: str = "utf-8",
    ) -> "Content":
        """Initializes Content from a string of text."""

        data = text.encode(encoding)
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)

        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype,
            extension=extension,
            filename=None,
            buffer=data
        )
        filename = default_filename(extension or "")

        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": 'text',
            "input_type": str(type(text)),
            "extra": metadata,
            "path": None,
            "extension": extension,
            "encoding": encoding,
        }
        return cls(**resolved_args)

    @classmethod
    def from_base64(
        cls: Type["Content"],
        b64_data: str | bytes,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: MetadataType = {},
    ) -> "Content":
        """Initializes Content from a base64 encoded string or bytes."""
        if isinstance(b64_data, str):
            b64_data = b64_data.encode('ascii')

        try:
            data = base64.b64decode(b64_data, validate=True)
        except (ValueError, TypeError) as e:
            raise ValueError("Invalid base64 data provided.") from e

        digest = hashlib.sha256(data).hexdigest()
        size = len(data)
        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype,
            extension=extension,
            filename=None,
            buffer=data
        )
        filename = default_filename(extension or "")

        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": "base64",
            "input_type": str(type(b64_data)),
            "extra": metadata,
            "path": None,
            "extension": extension,
            "encoding": "base64",
        }
        return cls(**resolved_args)

    @classmethod
    def from_path(
        cls: Type["Content"],
        path: str | Path,
        /,
        encoding: str = "utf-8",
        mimetype: str | None = None,
        metadata: MetadataType = {},
    ) -> "Content":
        """Initializes Content from a local file path."""
        path_obj = Path(path)
        if not is_valid_path(path_obj):
            raise FileNotFoundError(f"File not found at path: {path_obj}")

        data = path_obj.read_bytes()
        file_name = path_obj.name
        file_size = path_obj.stat().st_size
        digest = hashlib.sha256(data).hexdigest()

        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype,
            extension=path_obj.suffix.lstrip('.'),
            filename=file_name,
            buffer=data
        )

        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": file_size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": file_name,
            "content_type": "file",
            "input_type": str(type(path)),
            "extra": metadata,
            "path": str(path_obj.resolve()),
            "extension": extension,
            "encoding": encoding,
        }
        return cls(**resolved_args)
