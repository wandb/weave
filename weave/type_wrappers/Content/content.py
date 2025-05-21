import os
from pathlib import Path
import subprocess
import logging
import sys
from typing import Generic
from typing_extensions import TypeVar
logger = logging.getLogger(__name__)
from .utils import (
    ContentMetadata,
    ContentProperties,
    normalize_args,
    normalize_file_args,
    normalize_bytes_args,
    normalize_base64_args,
)

T = TypeVar("T", bound=str)

class Content(Generic[T]):
    """A class representing a file, raw bytes or base64 content with path, mimetype, and size information."""
    properties: ContentProperties

     # Take a type hint which can be either extension or mimetype so that the annotation parser doesn't have to deal with it
    def __init__(
        self,
        input: bytes | str | Path | ContentProperties,
        type_hint: str | None = None,
        mimetype: str | None = None,
        extension: str | None = None,
    ):
        if not mimetype and not extension:
            if type_hint:
                if type_hint.startswith(".") or type_hint.index('/') == -1:
                    extension = type_hint
                else:
                    mimetype = type_hint
                mimetype = type_hint
        if not isinstance(input, dict):
            self.properties = normalize_args(input, mimetype, extension)
            return

        self.properties = input

    # For backwards compatibility
    @classmethod
    def from_path(cls, path: Path, mimetype=None, extension=None):
        cls(normalize_file_args(path, mimetype, extension))

    # For backwards compatibility
    @classmethod
    def from_bytes(cls, data: bytes, mimetype=None, extension=None):
        cls(normalize_bytes_args(data, mimetype, extension))

    # For backwards compatibility
    @classmethod
    def from_base64(cls, data: str | bytes, mimetype=None, extension=None):
        if isinstance(data, bytes):
            data = data.decode("ascii")
        cls(normalize_base64_args(data, mimetype, extension))

    @property
    def data(self) -> bytes:
        """Get the raw content data."""
        return self.properties["data"]

    @property
    def mimetype(self) -> str:
        """Get the MIME type of the content."""
        return self.properties["mimetype"]

    @property
    def extension(self) -> str:
        """Get the file extension of the content."""
        return self.properties["extension"]

    @property
    def filename(self) -> str:
        return self.properties["filename"]

    @property
    def original_path(self) -> str | None:
        return self.properties["original_path"]

    @property
    def size(self) -> int:
        return self.properties["size"]

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

    @property
    def pyclass(self) -> str:
        return self.properties["pyclass"]

    @property
    def class_id(self) -> str:
        return self.properties["pyclass"]

    @property
    def metadata(self) -> ContentMetadata:
        """Get the metadata of the content.
        Returns:
            dict: A dictionary containing the metadata of the content.
        """
        return {
            "mimetype": self.mimetype,
            "extension": self.extension,
            "filename": self.filename,
            "original_path": self.original_path,
            "size": self.size,
            "pyclass": "weave.Content"
        }

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

