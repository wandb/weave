from __future__ import annotations

import base64
import hashlib
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Annotated, Any, Generic

from pydantic import BaseModel, Field, PrivateAttr
from typing_extensions import Self, TypeVar

from weave.trace.refs import Ref
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact

from .content_types import ContentType, ResolvedContentArgs, ValidContentInputs

logger = logging.getLogger(__name__)

# Dummy typevar to allow for passing mimetype/extension through annotated content
# e.x. Content["pdf"] or Content["application/pdf"]
T = TypeVar("T", bound=str)


class Content(BaseModel, Generic[T]):
    """
    A class to represent content from various sources, resolving them
    to a unified byte-oriented representation with associated metadata.

    This class must be instantiated using one of its classmethods:
    - from_path()
    - from_bytes()
    - from_text()
    - from_base64()
    """

    # This is required due to some attribute setting done by our serialization layer
    # Without it, it is hard to know if it was processed properly
    id: str
    data: bytes
    size: int
    mimetype: str
    digest: str
    filename: str
    content_type: ContentType
    input_type: str

    encoding: str = Field(
        "utf-8", description="Encoding to use when decoding bytes to string"
    )

    metadata: Annotated[
        dict[str, Any] | None,
        Field(
            description="metadata metadata to associate with the content",
            examples=[{"number of cats": 1}],
        ),
    ] = None
    path: str | None = None
    extension: str | None = None

    _last_saved_path: Annotated[
        str | None, Field(description="Last path the file was saved to")
    ] = None

    # These fields are set by serialization layer when it picks up a pydantic class
    # We define them here so they can be set without doing `extra=allow`
    _ref: Ref | None = PrivateAttr(None)
    _art: MemTraceFilesArtifact | None = PrivateAttr(None)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Direct initialization is disabled.
        Please use a classmethod like `Content.from_path()` to create an instance.
        """
        raise NotImplementedError(
            "Content objects cannot be initialized directly."
            "For best results use a classmethod: from_path, from_bytes, from_text, or from_base64."
            "If you must accept arbitrary inputs, Content._from_guess infers which method to use."
        )

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
        from .utils import default_filename, full_name, get_mime_and_extension

        if len(data) == 0:
            logger.warning("Content.from_bytes received empty data")

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
            "input_type": full_name(data),
            "extension": extension,
            "encoding": encoding,
        }

        if metadata:
            resolved_args["metadata"] = metadata

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
        from .utils import default_filename, full_name, get_mime_and_extension

        if len(text) == 0:
            logger.warning("Content.from_text received empty text")

        data = text.encode(encoding)
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)

        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype,
            extension=extension,
            filename=None,
            buffer=data,
            default_mimetype="text/plain",
            default_extension=".txt",
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
            "input_type": full_name(text),
            "extension": extension,
            "encoding": encoding,
        }

        if metadata:
            resolved_args["metadata"] = metadata

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
        from .utils import default_filename, full_name, get_mime_and_extension

        if len(b64_data) == 0:
            logger.warning("Content.from_base64 received empty input")

        input_type = full_name(b64_data)
        if isinstance(b64_data, str):
            b64_data = b64_data.encode("ascii")
        try:
            if len(b64_data) == 0:
                data = b""
            else:
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
            resolved_args["metadata"] = metadata

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
        from .utils import full_name, get_mime_and_extension, is_valid_path

        path_obj = Path(path)
        if not is_valid_path(path_obj):
            raise FileNotFoundError(f"File not found at path: {path_obj}")

        data = path_obj.read_bytes()
        file_name = path_obj.name
        file_size = path_obj.stat().st_size
        digest = hashlib.sha256(data).hexdigest()

        if file_size == 0:
            logger.warning("Content.from_path received empty file")

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
            "input_type": full_name(path),
            "path": str(path_obj.resolve()),
            "extension": extension,
            "encoding": encoding,
        }

        if metadata:
            resolved_args["metadata"] = metadata

        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def _from_guess(
        cls: type[Self],
        input: ValidContentInputs,
        /,
        extension: str | None = None,
        mimetype: str | None = None,
    ) -> Self:
        from .utils import is_valid_b64, is_valid_path

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

    def as_string(self) -> str:
        """
        Display the data as a string. Bytes are decoded using the `encoding` attribute
        If base64, the data will be re-encoded to base64 bytes then decoded to an ASCII string
        Returns:
            str
        """
        if self.encoding == "base64":
            return base64.b64encode(self.data).decode("ascii")
        return self.data.decode(encoding=self.encoding)

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

    # These methods are just here so that we can keep both ref and art as private attributes.
    # This way the serialization and ref tracking layers can access and set them as needed
    # But they will be totally ignored with regards to the pydantic model
    @property
    def ref(self) -> Any:
        return self._ref

    @ref.setter
    def ref(self, value: Any) -> None:
        self._ref = value

    @property
    def art(self) -> Any:
        return self._art

    @art.setter
    def art(self, value: Any) -> None:
        self._art = value
