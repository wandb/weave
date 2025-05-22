from collections.abc import Callable
import inspect
from pathlib import Path
from typing import Any, TypeVar
from typing import Any, Generic
from pydantic import BaseModel
import subprocess
import sys
import os
import logging
import base64
from weave.type_wrappers.Content.mime_resolver import get_mime_and_extension

logger = logging.getLogger(__name__)

TO_BYTES_METHODS = [
    'tobytes', # Numpy, Pandas, etc
    'to_bytes', # Some custom classes and int
    'read', # File-like objects
    'read_bytes', # File-like objects, Path, etc
    'as_bytes', # Some custom classes
]

CONTENT_KWARGS = [
    'filename',
    'path',
    'extension',
    'mimetype',
]

def default_name_fn(mimetype: str, extension: str) -> str:
    return mimetype.split("/")[1] + "." + extension

def is_valid_path(input: str | Path) -> bool:
    if isinstance(input, str):
        input = Path(input)
    return input.exists() and input.is_file()

def resolve_filename(
    default_fn: Callable[..., str] = default_name_fn,
    **kwargs
) -> str:
    if filename := kwargs.get("filename", None):
        return filename
    elif path := kwargs.get("path", None):
        return Path(path).name

    return default_fn(**kwargs)


class BaseContentHandler(BaseModel):
    size: int
    filename: str
    mimetype: str
    extension: str
    data: bytes
    extra: dict[str, Any] = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for key, value in kwargs.items():
            if key not in self.model_fields_set:
                self.extra[key] = value

    @property
    def metadata(self) -> dict[str, Any]:
        metadata = self.model_dump(exclude={"data", "extra"})
        for key, value in self.extra.items():
            metadata[key] = value
        return metadata


class BytesContentHandler(BaseContentHandler):
    def __init__(self, input: bytes, **kwargs):
        size = kwargs.pop("size", None) or len(input)
        mimetype = kwargs.pop("mimetype", None)
        extension = kwargs.pop("extension", None)

        if not mimetype or not extension:
            mimetype, extension = get_mime_and_extension(
                buffer=input[:2048],
                **kwargs
            )

        filename = kwargs.pop('filename', None)
        if not filename:
            filename = resolve_filename(mimetype=mimetype, extension=extension, **kwargs)

        original_path = kwargs.get("path", None)

        extra = kwargs.pop("extra", {})
        if original_path is not None:
            extra['original_path'] = original_path
        kwargs['extra'] = extra

        super().__init__(
            size=size,
            data=input,
            filename=filename,
            extension=extension,
            mimetype=mimetype,
            **kwargs
        )

class FileInput(BytesContentHandler):
    def __init__(self, input: str | Path, **kwargs):
        if not is_valid_path(input):
            raise ValueError(f"Input {input} is not a valid file path.")

        path = Path(input)
        size = path.stat().st_size

        data = path.read_bytes()
        # # Allow overriding the filename
        filename = kwargs.pop("filename", path.name)
        super().__init__(
            input=data,
            size=size,
            filename=filename,
            **kwargs
        )

class Base64ContentHandler(BytesContentHandler):
    def __init__(self, input: str | bytes, **kwargs):
        try:
            data = base64.b64decode(input, validate=True)
            super().__init__(data, **kwargs)
        except Exception as e:
            raise ValueError(f"Invalid base64 string: {e}") from e

class ObjectContentHandler(BytesContentHandler):
    def __init__(self, input: object, **kwargs):
        if not input.__getattribute__('__class__'):
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
        super().__init__(data, **kwargs)

T = TypeVar("T", bound=str)

class Content(Generic[T]):
    content_handler: BaseContentHandler

    def __init__(
        self,
        input: Any,
        type_hint: str | None = None,
        **kwargs
    ):
        if type_hint:
            if type_hint.find("/") != -1:
                kwargs["mimetype"] = type_hint
            else:
                kwargs["extension"] = type_hint.lstrip(".")

        if isinstance(input, Path):
            self.content_handler = FileInput(str(input), **kwargs)
        elif isinstance(input, str):
            if is_valid_path(str(input)):
                self.content_handler = FileInput(str(input), **kwargs)
            else:
                try:
                    self.content_handler = Base64ContentHandler(str(input), **kwargs)
                except ValueError:
                    raise ValueError(
                        f"Could not parse string {input} as a valid path or base64 string"
                    )
        elif isinstance(input, bytes):
            self.content_handler = BytesContentHandler(input, **kwargs)
        elif hasattr(input, "__class__"):
            self.content_handler = ObjectContentHandler(input, **kwargs)
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
        return self.content_handler.extra.get("original_path", None)

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
