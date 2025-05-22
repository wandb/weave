import base64
import inspect
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar, Unpack

from pydantic import BaseModel

from weave.type_wrappers.Content.utils import (
    ContentKeywordArgs,
    ContentOptionalArgs,
    default_filename,
    get_mime_and_extension,
    is_valid_path,
)

logger = logging.getLogger(__name__)

TO_BYTES_METHODS = [
    "tobytes",  # Numpy, Pandas, etc
    "to_bytes",  # Some custom classes and int
    "read",  # File-like objects
    "read_bytes",  # File-like objects, Path, etc
    "as_bytes",  # Some custom classes
]


class BaseContentHandler(BaseModel):
    size: int
    filename: str
    mimetype: str
    extension: str
    data: bytes
    path: str | None = None

    def __init__(self, data: bytes, /, **values: Any):
        if "extra" in values.keys():
            extra = values.pop("extra") or {}
        else:
            extra = {}

        for k in values:
            if k in self.model_fields_set:
                raise ValueError(f"Got invalid extra metadata field: {k}")
        super().__init__(data=data, **{**values, **extra})

    @property
    def metadata(self) -> dict[str, Any]:
        return self.model_dump(exclude={"data"}, exclude_unset=True, exclude_none=True)


class BytesContentHandler(BaseContentHandler):
    def __init__(self, input: bytes, /, **values: Any):
        values["size"] = values["size"] or len(input)
        if values["mimetype"] is None or values["extension"] is None:
            mimetype, extension = get_mime_and_extension(
                buffer=input[:2048],
                filename=values["filename"],
                extension=values["extension"],
                mimetype=values["mimetype"],
            )
            values["mimetype"] = mimetype
            values["extension"] = extension
        values["filename"] = values["filename"] or default_filename(values["extension"])

        super().__init__(input, **values)


class FileContentHandler(BytesContentHandler):
    def __init__(self, input: str | Path, **values: Any):
        if not is_valid_path(input):
            raise ValueError(f"Input {input} is not a valid file path.")

        path = Path(input)
        values["path"] = path
        values["size"] = path.stat().st_size
        # Allow overriding the filename when submitting to weave
        values["filename"] = values.get("filename", path.name)
        data = path.read_bytes()
        super().__init__(data, **values)


class Base64ContentHandler(BytesContentHandler):
    def __init__(self, input: str | bytes, **values: Unpack[ContentOptionalArgs]):
        try:
            data = base64.b64decode(input, validate=True)
            super().__init__(data, **values)
        except Exception as e:
            raise ValueError(f"Invalid base64 string: {e}") from e


class ObjectContentHandler(BytesContentHandler):
    def __init__(self, input: object, **values: Unpack[ContentOptionalArgs]):
        if not input.__getattribute__("__class__"):
            raise ValueError("Input object does not have a class attribute.")

        handler: Callable[..., bytes] | None = None

        class_members = inspect.getmembers(input.__class__)
        for name, _ in class_members:
            if name in TO_BYTES_METHODS:
                handler = getattr(input, name)

        if handler is None:
            raise ValueError(
                """
                No valid method found to convert object to bytes.
                If your object has a method to convert to bytes, please supply the name
                in the the to_bytes keyword arguement
                """
            )

        data = handler()
        super().__init__(data, **values)


T = TypeVar("T", bound=str)


class Content(Generic[T]):
    """
    This is similar to a factory but uses the instance as an attribute so we can
    benefit from the organization of the content handlers without having to
    manage the object recognition for the weave serializers
    """

    content_handler: BaseContentHandler

    def __init__(
        self,
        input: Any,
        type_hint: str | None = None,
        /,
        **values: Unpack[ContentKeywordArgs],
    ):
        if type_hint:
            if type_hint.find("/") != -1:
                values["mimetype"] = type_hint
            else:
                values["extension"] = type_hint.lstrip(".")

        values_with_defaults = ContentOptionalArgs(
            filename=values.get("filename", None),
            path=values.get("path", None),
            extension=values.get("extension", None),
            mimetype=values.get("mimetype", None),
            size=values.get("size", None),
            extra=values.get("extra", {}),
        )

        if isinstance(input, Path):
            self.content_handler = FileContentHandler(
                str(input), **values_with_defaults
            )
        elif isinstance(input, str):
            if is_valid_path(str(input)):
                self.content_handler = FileContentHandler(
                    str(input), **values_with_defaults
                )
            else:
                try:
                    self.content_handler = Base64ContentHandler(
                        str(input), **values_with_defaults
                    )
                except ValueError:
                    raise ValueError(
                        f"Could not parse string {input} as a valid path or base64 string"
                    )
        elif isinstance(input, bytes):
            self.content_handler = BytesContentHandler(input, **values_with_defaults)
        elif hasattr(input, "__class__"):
            self.content_handler = ObjectContentHandler(input, **values_with_defaults)
        else:
            raise ValueError(f"Unsupported input type: {type(input)}")

    @property
    def metadata(self) -> dict[str, Any]:
        return self.content_handler.metadata

    @property
    def data(self) -> bytes:
        return self.content_handler.data

    @property
    def size(self) -> int:
        return self.content_handler.size

    @property
    def filename(self) -> str:
        return self.content_handler.filename

    @property
    def original_path(self) -> str | None:
        return self.content_handler.metadata.get("original_path")

    @property
    def extension(self) -> str:
        return self.content_handler.extension

    @property
    def mimetype(self) -> str:
        return self.content_handler.mimetype

    def open(self) -> bool:
        """Open the file using the operating system's default application.

        This method uses the platform-specific mechanism to open the file with
        the default application associated with the file's type.

        Returns:
            bool: True if the file was successfully opened, False otherwise.
        """
        if not self.original_path:
            # TODO: Tempfile
            return False

        try:
            if sys.platform == "win32":
                os.startfile(self.path)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(("open", str(self.original_path)))
            else:  # linux variants
                subprocess.call(("xdg-open", str(self.path)))
        except Exception as e:
            logger.exception(f"Failed to open file {self.original_path}: {e}")
            return False
        return True

    def save(self, dest: str | Path) -> None:
        """Copy the file to the specified destination path.

        Args:
            dest: Destination path where the file will be copied to (string or pathlib.Path)
                  The destination path can be a file or a directory.
        """
        path = Path(dest) if isinstance(dest, str) else dest
        os.makedirs(path.parent, exist_ok=True)

        # Otherwise write the data to the path
        with open(path, "wb") as f:
            f.write(self.data)
