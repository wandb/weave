from __future__ import annotations

import logging
import os
import subprocess
import sys
import base64
import hashlib
from typing_extensions import Self
import uuid
from pathlib import Path
from typing import Annotated, Generic, Type, TypeVar
from pydantic import Field, BaseModel
from utils import (
    get_mime_and_extension,
    default_filename,
    is_valid_path,
)
from content_types import (
    ContentType,
    MetadataType,
    ResolvedContentArgs,
)

logger = logging.getLogger(__name__)

ValidContentInput = str | bytes | Path

def _is_file_input(input: str | Path):
    if isinstance(input, Path):
        return True
    return is_valid_path(input)

def _is_base64_input(input: str | bytes):
    # Normalize to bytes
    if isinstance(input, str):
        input = input.encode('ascii')
    try:
       _ = base64.b64decode(input, validate=True)
    except (ValueError, TypeError) as _:
        return False

    return True

# Dummy typevar to allow for passing mimetype/extension through annotated content
# e.x. Content["pdf"] or Content["application/pdf"]
T = TypeVar("T", bound=str)

class Content(Generic[T], BaseModel):
    """
    A class to represent content from various sources, resolving them
    to a unified byte-oriented representation with associated metadata.

    The default constructor initializes content from a file path.
    """

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

    def __init__(
        self,
        input: ValidContentInput,
        /,
        encoding: str | None = None,
        mimetype: str | None = None,
        extension: str | None = None,
        metadata: MetadataType = {},
    ):
        if isinstance(input, (Path, str)) and _is_file_input(input):
            # Do not pass extension because it should be determined from filename
            return self.from_path(
                input,
                mimetype=mimetype,
                metadata=metadata,
                encoding=encoding or "utf-8"
            )
        elif isinstance(input, (bytes, str)) and _is_base64_input(input):
            # Do not pass encoding because it should be base64
            return self.from_base64(
                input,
                extension=extension,
                mimetype=mimetype,
                metadata=metadata,
            )
        elif isinstance(input, str): # If string -> we know it is not a path or base64 so must be text
            return self.from_text(
                input,
                extension=extension,
                mimetype=mimetype,
                metadata=metadata,
                encoding=encoding or "utf-8"
            )
        elif isinstance(input, bytes): # If bytes -> we know it is not a base64 so must be bytes
            return self.from_bytes(
                input,
                extension=extension,
                mimetype=mimetype,
                metadata=metadata,
                encoding=encoding or "utf-8"
            )
        else:
            raise TypeError(f"Unsupported input type: {type(input)}")


    @classmethod
    def from_bytes(
        cls: Type[Self],
        data: bytes,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: MetadataType = {},
        encoding: str = "utf-8",
    ) -> Self:
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
        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_text(
        cls: Type[Self],
        text: str,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: MetadataType = {},
        encoding: str = "utf-8",
    ) -> Self:
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
        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_base64(
        cls: Type[Self],
        b64_data: str | bytes,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: MetadataType = {},
    ) -> Self:
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
            "content_type": 'base64',
            "input_type": str(type(b64_data)),
            "extra": metadata,
            "path": None,
            "extension": extension,
            "encoding": "base64",
        }
        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_path(
        cls: Type[Self],
        path: str | Path,
        /,
        encoding: str = "utf-8",
        mimetype: str | None = None,
        metadata: MetadataType = {},
    ) -> Self:
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

        # We gather all the resolved arguments...
        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": file_size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": file_name,
            "content_type": 'file',
            "input_type": str(type(path)),
            "extra": metadata,
            "path": str(path_obj.resolve()),
            "extension": extension,
            "encoding": encoding,
        }
        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def _from_resolved_args(cls: Type[Self], /, args: ResolvedContentArgs) -> Self:
        """
        Initializes Content from pre-existing ResolvedContentArgs
        This is for internal use to reconstruct the Content object by the serialization layer
        """
        return cls.model_construct(**args)

    def open(self) -> bool:
        """Open the file using the operating system's default application.

        This method uses the platform-specific mechanism to open the file with
        the default application associated with the file's type.

        Returns:
            bool: True if the file was successfully opened, False otherwise.
        """
        path = self._last_saved_path or self.path

        if not path:
            logger.exception(
                "Opening unsaved files is not supported. Please run Content.save() and try running Content.open() again.",
                exc_info=False,
            )
            return False

        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(("open", str(path)))
            else:  # linux variants
                subprocess.call(("xdg-open", str(path)))
        except Exception as e:
            logger.exception(f"Failed to open file {path}: {e}")
            return False
        return True

    def save(self, dest: str | Path) -> None:
        """Copy the file to the specified destination path.
        Updates the filename and the path of the content to reflect the last saved copy

        Args:
            dest: Destination path where the file will be copied to (string or pathlib.Path)
                  The destination path can be a file or a directory.
                  If dest has no file extension (e.g. .txt), destination will be considered a directory.
        """
        path = Path(dest) if isinstance(dest, str) else dest

        if (path.exists() and path.is_dir()) or not path.suffix:
            path = path.joinpath(self.filename)

        # Now we know path ends in a filename
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        # Write the data to the path
        with open(path, "wb") as f:
            f.write(self.data)

        # Update the last_saved_path to reflect the saved copy. This ensures open works.
        self._last_saved_path = str(path)
