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
    path: str | None = None
    model_config = ConfigDict(extra="allow")

    def __init__(self, data: bytes, /, **values: Any):
        super().__init__(data=data, **values)

    @property
    def metadata(self) -> dict[str, Any]:
        return self.model_dump(exclude={"data"})


def create_bytes_content(
    input: bytes, /, **values: Unpack[ContentArgs]
) -> BaseContentHandler:
    values["size"] = values["size"] or len(input)
    values["extra"]["input_type"] = values["extra"].get("input_type") or "bytes"
    values["extra"]["input_category"] = values["extra"].get("input_category") or "data"
    if values["mimetype"] is None or values["extension"] is None:
        mimetype, extension = get_mime_and_extension(
            buffer=input[:2048],
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
    values["extra"]["original_path"] = values["extra"].get("original_path") or str(path)
    values["extra"]["input_type"] = values["extra"].get("input_type") or "str"
    values["extra"]["input_category"] = values["extra"].get("input_category") or "path"
    data = path.read_bytes()
    return create_bytes_content(data, **values)


def create_b64_content(
    input: str | bytes, /, **values: Unpack[ContentArgs]
) -> BaseContentHandler:
    try:
        data = base64.b64decode(input, validate=True)
        values["extra"]["input_type"] = values["extra"].get("input_type") or str(
            type(input)
        )
        values["extra"]["input_category"] = (
            values["extra"].get("input_category") or "base64"
        )
        return create_bytes_content(data, **values)
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}") from e


T = TypeVar("T", bound=str)


class Content(Generic[T]):
    """
    This is similar to a factory but uses the instance as an attribute so we can
    benefit from the organization of the content handlers without having to
    manage the object recognition for the weave serializers
    """

    content_handler: BaseContentHandler
    _last_saved_path: str | None = None

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

        extra = values.get("extra", {})

        content_args: ContentArgs = {
            "filename": values.get("filename", None),
            "path": values.get("path", None),
            "extension": values.get("extension", None),
            "mimetype": values.get("mimetype", None),
            "size": values.get("size", None),
            "extra": extra,
        }

        if isinstance(input, Path):
            content_args["extra"]["input_type"] = content_args["extra"].get(
                "input_type"
            ) or str(input.__class__)
            content_args["extra"]["input_category"] = (
                content_args["extra"].get("input_category") or "object"
            )
            self.content_handler = create_file_content(str(input), **content_args)

        elif isinstance(input, str):
            if is_valid_path(input):
                self.content_handler = create_file_content(str(input), **content_args)
            else:
                try:
                    self.content_handler = create_b64_content(
                        str(input), **content_args
                    )
                except ValueError:
                    raise ValueError(
                        f"Could not parse string {input} as a valid path or base64 string"
                    )
        elif isinstance(input, bytes):
            self.content_handler = create_bytes_content(input, **content_args)
        else:
            raise TypeError(f"Unsupported input type: {type(input)}")

    @property
    def metadata(self) -> dict[str, Any]:
        return self.content_handler.metadata

    @property
    def input_type(self) -> str | None:
        """type or instance of the input - bytes, str, <class instance>"""
        # We keep this in extra because we never want to expose it directly to the user
        # This should be computed by first factory function and loaded from extra when deserializing
        return self.content_handler.extra.get("input_type")

    @property
    def input_category(self) -> str | None:
        """Category of the input - base64, path, data, object"""
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
    def path(self) -> str | None:
        return self.content_handler.path

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
        """
        path = Path(dest) if isinstance(dest, str) else dest
        os.makedirs(path.parent, exist_ok=True)

        # Otherwise write the data to the path
        with open(path, "wb") as f:
            f.write(self.data)

        # Update the last_saved_path to reflect the saved copy. This ensures open works.
        self._last_saved_path = str(dest)
