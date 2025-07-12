# content.py
from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from typing_extensions import Unpack

from weave.type_wrappers.Content.utils import (
    ContentArgs,
    ContentKeywordArgs,
    default_filename,
    get_mime_and_extension,
    is_valid_path,
)

logger = logging.getLogger(__name__)


class BaseContentHandler(BaseModel):
    size: int
    filename: str
    mimetype: str
    extension: str
    data: bytes
    extra: dict
    encoding: str
    path: str | None = None
    model_config = ConfigDict(extra="allow")

    def __init__(self, data: bytes, /, **values: Any):
        # Default here so when a factory calls a factory we can safely do the existence check
        values["encoding"] = values.get("encoding") or "utf-8"
        super().__init__(data=data, **values)

    @property
    def metadata(self) -> dict[str, Any]:
        return self.model_dump(exclude={"data"})


def create_bytes_content(
    input: bytes, /, **values: Unpack[ContentArgs]
) -> BaseContentHandler:
    values["size"] = values["size"] or len(input)
    values["extra"]["input_type"] = values["extra"].get("input_type", str(type(input)))
    values["extra"]["input_category"] = values["extra"].get("input_category", "data")
    # Raw binary data has no encoding unless explicitly provided
    if values["mimetype"] is None or values["extension"] is None:
        mimetype, extension = get_mime_and_extension(
            buffer=input,
            filename=values["filename"],
            extension=values["extension"],
            mimetype=values["mimetype"],
        )
        values["mimetype"] = mimetype
        values["extension"] = extension

    values["filename"] = values["filename"] or default_filename(
        str(values["extension"])
    )

    return BaseContentHandler(input, **values)


def create_file_content(
    input: str, /, **values: Unpack[ContentArgs]
) -> BaseContentHandler:
    if not is_valid_path(input):
        raise ValueError(f"Input {input} is not a valid file path.")

    path = Path(input)
    values["path"] = str(path)
    values["size"] = path.stat().st_size
    values["filename"] = path.name
    values["extra"]["original_path"] = values["extra"].get("original_path", str(path))
    values["extra"]["input_type"] = values["extra"].get("input_type", str(type(input)))
    values["extra"]["input_category"] = values["extra"].get("input_category", "path")
    data = path.read_bytes()
    return create_bytes_content(data, **values)


def create_b64_content(
    input: str | bytes, /, **values: Unpack[ContentArgs]
) -> BaseContentHandler:
    try:
        data = base64.b64decode(input, validate=True)
        values["extra"]["input_type"] = values["extra"].get(
            "input_type", str(type(input))
        )
        values["extra"]["input_category"] = values["extra"].get(
            "input_category", "base64"
        )
        # Set encoding to 'base64' for base64 encoded data
        values["encoding"] = "base64"
        result = create_bytes_content(data, **values)
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}") from e

    return result


T = TypeVar("T", bound=str)


class Content(Generic[T]):
    """
    A container for content, such as files, raw bytes, or base64 encoded strings.

    The primary constructor `Content()` accepts raw bytes. For other data types,
    use the appropriate classmethod constructors:
    - `Content.from_path()` for file paths.
    - `Content.from_bytes()` for binary data (alias for the constructor).
    - `Content.from_b64()` for base64 encoded strings.

    This class abstracts away the handling of different content sources, providing
    a uniform interface to access the data and its metadata.
    """

    content_handler: BaseContentHandler
    _last_saved_path: str | None

    def __init__(
        self,
        data: bytes,
        type_hint: str | None = None,
        /,
        **values: Unpack[ContentKeywordArgs],
    ):
        """
        Initializes Content from raw bytes. This is the primary constructor.

        Args:
            data: The binary data.
            type_hint: An optional hint for the mimetype or extension.
            **values: Additional keyword arguments for content properties.
        """
        content_args = self._prepare_content_args(type_hint, values)
        self.content_handler = create_bytes_content(data, **content_args)
        self._last_saved_path = None

    @staticmethod
    def _prepare_content_args(
        type_hint: str | None, values: ContentKeywordArgs
    ) -> ContentArgs:
        """Helper to process common constructor arguments."""
        if type_hint:
            if "/" in type_hint:
                values["mimetype"] = type_hint
            else:
                values["extension"] = type_hint.lstrip(".")

        extra = values.get("extra", {})

        return {
            "filename": values.get("filename", None),
            "path": values.get("path", None),
            "extension": values.get("extension", None),
            "mimetype": values.get("mimetype", None),
            "size": values.get("size", None),
            "encoding": values.get("encoding", None),
            "extra": extra,
        }

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        type_hint: str | None = None,
        /,
        **values: Unpack[ContentKeywordArgs],
    ) -> Content:
        """
        Creates a Content object from a file path.

        Args:
            path: The path to the file.
            type_hint: An optional hint for the mimetype or extension.
            **values: Additional keyword arguments for content properties.

        Returns:
            A new Content instance.

        Raises:
            FileNotFoundError: If the path does not exist or is not a file.
        """
        if not is_valid_path(path):
            raise FileNotFoundError(f"File not found or is not a file: {path}")

        path_obj = Path(path)
        data = path_obj.read_bytes()

        # Populate values with path-specific metadata if not already provided
        values.setdefault("filename", path_obj.name)
        values.setdefault("path", str(path_obj))
        values.setdefault("size", path_obj.stat().st_size)

        extra = values.setdefault("extra", {})
        extra.setdefault("original_path", str(path_obj))
        extra.setdefault("input_type", str(type(path)))
        extra.setdefault("input_category", "path")

        return cls(data, type_hint, **values)

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        type_hint: str | None = None,
        /,
        **values: Unpack[ContentKeywordArgs],
    ) -> Content:
        """
        Creates a Content object from raw bytes. Alias for `Content()`.

        Args:
            data: The binary data.
            type_hint: An optional hint for the mimetype or extension.
            **values: Additional keyword arguments for content properties.

        Returns:
            A new Content instance.
        """
        return cls(data, type_hint, **values)

    @classmethod
    def from_b64(
        cls,
        b64_string: str | bytes,
        type_hint: str | None = None,
        /,
        **values: Unpack[ContentKeywordArgs],
    ) -> Content:
        """
        Creates a Content object from a base64 encoded string.

        Args:
            b64_string: The base64 encoded string or bytes.
            type_hint: An optional hint for the mimetype or extension.
            **values: Additional keyword arguments for content properties.

        Returns:
            A new Content instance.
        """
        try:
            data = base64.b64decode(b64_string, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid base64 string: {e}") from e

        # Populate values with b64-specific metadata
        extra = values.setdefault("extra", {})
        extra.setdefault("input_type", str(type(b64_string)))
        extra.setdefault("input_category", "base64")
        values.setdefault("encoding", "base64")
        return cls(data, type_hint, **values)

    @property
    def metadata(self) -> dict[str, Any]:
        return self.content_handler.metadata

    @property
    def input_type(self) -> str | None:
        # type or instance of the input - bytes, str, class instance
        # We keep this in extra because we never want to expose it directly to the user
        # This should be computed by first factory function and loaded from extra when deserializing
        return self.content_handler.extra.get("input_type")

    @property
    def input_category(self) -> str | None:
        # Category of the input - base64, path, data, object
        # We keep this in extra because we never want to expose it directly to the user
        # This should be computed by first factory function and loaded from extra when deserializing
        return self.content_handler.extra.get("input_category")

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
    def extension(self) -> str:
        return self.content_handler.extension

    @property
    def mimetype(self) -> str:
        return self.content_handler.mimetype

    @property
    def encoding(self) -> str:
        return self.content_handler.encoding

    @property
    def path(self) -> str | None:
        return self.content_handler.path

    def as_string(self) -> str:
        return self.data.decode(self.encoding)

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
