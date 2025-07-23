from __future__ import annotations

import base64
import hashlib
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Annotated, Any, Generic, Literal, NotRequired, TypedDict, Union

from pydantic import BaseModel, Field
from typing_extensions import Self, TypeVar

from .utils import default_filename, get_mime_and_extension, is_valid_b64, is_valid_path

logger = logging.getLogger(__name__)

# Dummy typevar to allow for passing mimetype/extension through annotated content
# e.x. Content["pdf"] or Content["application/pdf"]
T = TypeVar("T", bound=str)

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

    # Optional fields - can be omitted or None
    extra: NotRequired[dict[str, Any]]
    path: NotRequired[str]
    extension: NotRequired[str]
    encoding: NotRequired[str]


class ResolvedContentArgs(ResolvedContentArgsWithoutData):
    # Required Fields
    data: bytes


class Content(BaseModel, Generic[T]):
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

    extra: Annotated[
        dict[str, Any] | None,
        Field(
            description="Extra metadata to associate with the content",
            examples=[{"number of cats": 1}],
        ),
    ] = None
    encoding: str | None = "utf-8"
    path: str | None = None
    extension: str | None = None

    _last_saved_path: Annotated[
        str | None,
        Field(description="Last path the file was saved to"),
    ] = Field(None, exclude=True)

    def __init__(
        self,
        path: str | Path,
        /,
        encoding: str = "utf-8",
        mimetype: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
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
            extension=path_obj.suffix,
            filename=file_name,
            buffer=data,
        )

        # We gather all the resolved arguments...
        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": file_size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": file_name,
            "content_type": "file",
            "input_type": str(type(path)),
            "path": str(path_obj.resolve()),
            "extension": extension,
            "encoding": encoding,
        }

        if metadata:
            resolved_args["extra"] = metadata

        super().__init__(**resolved_args)

    @classmethod
    def from_bytes(
        cls: type[Self],
        data: bytes,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: dict[str, Any] | None = None,
        encoding: str = "utf-8",
    ) -> Self:
        """Initializes Content from raw bytes."""
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)
        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype, extension=extension, filename=None, buffer=data
        )
        filename = default_filename(
            extension=extension, mimetype=mimetype, digest=digest
        )

        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": "bytes",
            "input_type": str(type(data)),
            "extra": metadata or {},
            "extension": extension,
            "encoding": encoding or "utf-8",
        }

        if metadata:
            resolved_args["extra"] = metadata

        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_text(
        cls: type[Self],
        text: str,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: dict[str, Any] | None = None,
        encoding: str = "utf-8",
    ) -> Self:
        """Initializes Content from a string of text."""
        data = text.encode(encoding)
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)
        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype, extension=extension, filename=None, buffer=data
        )
        filename = default_filename(
            extension=extension, mimetype=mimetype, digest=digest
        )

        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": "text",
            "input_type": str(type(text)),
            "extension": extension,
            "encoding": encoding,
        }

        if metadata:
            resolved_args["extra"] = metadata

        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_base64(
        cls: type[Self],
        b64_data: str | bytes,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        """Initializes Content from a base64 encoded string or bytes."""
        input_type = str(type(b64_data))
        if isinstance(b64_data, str):
            b64_data = b64_data.encode("ascii")
        try:
            data = base64.b64decode(b64_data, validate=True)
        except (ValueError, TypeError) as e:
            raise ValueError("Invalid base64 data provided.") from e

        digest = hashlib.sha256(data).hexdigest()
        size = len(data)
        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype, extension=extension, filename=None, buffer=data
        )
        filename = default_filename(
            extension=extension, mimetype=mimetype, digest=digest
        )

        resolved_args: ResolvedContentArgs = {
            "id": uuid.uuid4().hex,
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": "base64",
            "input_type": input_type,
            "extension": extension,
            "encoding": "base64",
        }

        if metadata:
            resolved_args["extra"] = metadata

        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_path(
        cls: type[Self],
        path: str | Path,
        /,
        encoding: str = "utf-8",
        mimetype: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        """Initializes Content from a local file path."""
        # This classmethod delegates to the main constructor
        return cls(path, encoding=encoding, mimetype=mimetype, metadata=metadata)

    @classmethod
    def _from_guess(
        cls: type[Self],
        input: bytes | str | Path,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
    ) -> Self:
        # First check if it is a path, we only check validity for str scenario
        # because we have dedicated error message for invalid path
        if isinstance(input, Path) or (isinstance(input, str) and is_valid_path(input)):
            return cls.from_path(input, mimetype=mimetype)

        # Then check if it is base64
        elif isinstance(input, (bytes, str)) and is_valid_b64(input):
            return cls.from_base64(input, mimetype=mimetype, extension=extension)

        # If it is still a str - treat as raw text
        elif isinstance(input, str):
            return cls.from_text(input, mimetype=mimetype, extension=extension)

        return cls.from_bytes(input, mimetype=mimetype, extension=extension)

    @classmethod
    def _from_resolved_args(cls: type[Self], /, args: ResolvedContentArgs) -> Self:
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
            logger.exception("Failed to open file %s", self.path)
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
        path = Path(dest)

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
