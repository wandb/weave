from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, Generic
from urllib.parse import quote_from_bytes, urlparse

from pydantic import BaseModel, Field, PrivateAttr, field_serializer
from typing_extensions import Self, TypeVar

from weave.trace.refs import Ref
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.type_wrappers.Content.content_types import (
    ContentType,
    ResolvedContentArgs,
    ValidContentInputs,
)
from weave.type_wrappers.Content.utils import (
    default_filename,
    full_name,
    get_mime_and_extension,
    is_valid_b64,
    is_valid_path,
    match_data_url,
    try_parse_data_url,
)

logger = logging.getLogger(__name__)

# Dummy typevar to allow for passing mimetype/extension through annotated content
# e.x. Content["pdf"] or Content["application/pdf"]
T = TypeVar("T", bound=str)


class Content(BaseModel, Generic[T]):
    """A class to represent content from various sources, resolving them
    to a unified byte-oriented representation with associated metadata.

    This class must be instantiated using one of its classmethods:
    - from_path()
    - from_bytes()
    - from_text()
    - from_url()
    - from_base64()
    - from_data_url()
    """

    # This is required due to some attribute setting done by our serialization layer
    # Without it, it is hard to know if it was processed properly
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
    extension: str | None = None

    _last_saved_path: Annotated[
        str | None, Field(description="Last path the file was saved to")
    ] = None

    # These fields are set by serialization layer when it picks up a pydantic class
    # We define them here so they can be set without doing `extra=allow`
    _ref: Ref | None = PrivateAttr(None)
    _art: MemTraceFilesArtifact | None = PrivateAttr(None)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Direct initialization is disabled.
        Please use a classmethod like `Content.from_path()` to create an instance.
        """
        raise NotImplementedError(
            "Content objects cannot be initialized directly."
            "For best results use a classmethod: from_path, from_bytes, from_text, or from_base64."
            "If you must accept arbitrary inputs, Content._from_guess infers which method to use."
        )

    @classmethod
    def model_validate(
        cls: type[Self],
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        """Override model_validate to handle Content reconstruction from dict."""
        if isinstance(obj, dict):
            # Check if this is a full Content dict (from deserialization)
            required_fields = {
                "data",
                "size",
                "mimetype",
                "digest",
                "filename",
                "content_type",
                "input_type",
            }
            if required_fields.issubset(obj.keys()):
                # Handle data field deserialization
                data = obj.get("data")
                if isinstance(data, str):
                    # Check if it was base64 encoded during serialization
                    content_type = obj.get("content_type", "")
                    if "base64" in content_type:
                        # Decode from base64
                        obj["data"] = base64.b64decode(data)
                    else:
                        # Decode from string using encoding
                        encoding = obj.get("encoding", "utf-8")
                        obj["data"] = data.encode(encoding)
                # Use model_construct to bypass __init__
                return cls.model_construct(**obj)

        # Fall back to parent implementation for other cases
        return super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context
        )

    @classmethod
    def model_validate_json(
        cls: type[Self],
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        """Override model_validate_json to handle Content reconstruction from JSON."""
        # Parse the JSON
        if isinstance(json_data, (bytes, bytearray)):
            json_data = json_data.decode("utf-8")
        obj = json.loads(json_data)

        # Use our custom model_validate
        return cls.model_validate(obj, strict=strict, context=context)

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
            "data": data,
            "size": file_size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": file_name,
            "content_type": "file",
            "input_type": full_name(path),
            "extension": extension,
            "encoding": encoding,
        }

        if metadata:
            resolved_args["metadata"] = metadata

        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_data_url(
        cls: type[Self], url: str, /, metadata: dict[str, Any] | None = None
    ) -> Self:
        """Initializes Content from a data URL."""
        parsed = try_parse_data_url(url)
        if not parsed:
            raise ValueError("Invalid data URL provided.")

        content_type = parsed.params.content_type
        encoding = parsed.params.encoding
        data = parsed.params.data
        mimetype = parsed.params.mimetype

        digest = hashlib.sha256(data).hexdigest()
        size = len(data)

        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype, extension=None, filename=None, buffer=data
        )
        filename = default_filename(
            extension=extension, mimetype=mimetype, digest=digest
        )

        resolved_args: ResolvedContentArgs = {
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": content_type,
            "input_type": full_name(url),
            "extension": extension,
            "encoding": encoding,
        }

        if metadata:
            resolved_args["metadata"] = metadata

        # Use model_construct to bypass our custom __init__
        return cls.model_construct(**resolved_args)

    @classmethod
    def from_url(
        cls: type[Self],
        url: str,
        /,
        headers: dict[str, Any] | None = None,
        timeout: int | None = 30,
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        """Initializes Content by fetching bytes from an HTTP(S) URL.

        Downloads the content, infers mimetype/extension from headers, URL path,
        and data, and constructs a Content object from the resulting bytes.
        """
        # Use our shared HTTP session with logging adapter
        # Local import to prevent importing requests unless necessary
        from weave.utils import http_requests as http_requests

        resp = http_requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()

        data = resp.content or b""
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)

        # Try to get mimetype from header (strip any charset)
        header_ct = resp.headers.get("Content-Type", "")
        mimetype_from_header = header_ct.split(";")[0].strip() if header_ct else None

        # Try to get filename from Content-Disposition or URL path
        filename_from_header = None
        cd = resp.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            # naive extraction; handles filename="..." or filename=...
            match = re.search(
                r"filename\*=.*?''([^;\r\n]+)|filename=\"?([^;\r\n\"]+)\"?", cd
            )
            if match:
                filename_from_header = match.group(1) or match.group(2)

        parsed_url = urlparse(url)
        url_basename = Path(parsed_url.path).name if parsed_url.path else None
        filename_hint = filename_from_header or url_basename

        mimetype, extension = get_mime_and_extension(
            mimetype=mimetype_from_header,
            extension=Path(filename_hint).suffix if filename_hint else None,
            filename=filename_hint,
            buffer=data,
        )

        filename = (
            filename_hint
            if filename_hint
            else default_filename(extension, mimetype, digest)
        )

        resolved_args: ResolvedContentArgs = {
            "data": data,
            "size": size,
            "mimetype": mimetype,
            "digest": digest,
            "filename": filename,
            "content_type": "bytes",
            "input_type": full_name(url),
            "extension": extension,
            # Use requests-detected encoding if present, else utf-8
            "encoding": resp.encoding or "utf-8",
        }

        if metadata:
            resolved_args["metadata"] = metadata

        return cls.model_construct(**resolved_args)

    @classmethod
    def _from_guess(
        cls: type[Self],
        input: ValidContentInputs,
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
            if match_data_url(input):
                return cls.from_data_url(input)
            # Match http or https URLs
            if re.match(r"^https?://", input):
                return cls.from_url(input)

            return cls.from_text(input, mimetype=mimetype, extension=extension)

        return cls.from_bytes(input, mimetype=mimetype, extension=extension)

    @classmethod
    def _from_resolved_args(cls: type[Self], /, args: ResolvedContentArgs) -> Self:
        """Initializes Content from pre-existing ResolvedContentArgs
        This is for internal use to reconstruct the Content object by the serialization layer.
        """
        return cls.model_construct(**args)

    def to_data_url(self, use_base64: bool = True) -> str:
        """Constructs a data URL from the content.

        Args:
            use_base64: If True, the data will be base64 encoded.
                        Otherwise, it will be percent-encoded. Defaults to True.

        Returns:
            A data URL string.
        """
        header = f"data:{self.mimetype}"
        if (
            self.mimetype.startswith("text/")
            and self.content_type.find(":encoding") != -1
        ):
            # Only add charset for text types
            header += f";charset={self.encoding}"

        if use_base64 or self.content_type.find(":base64"):
            encoded_data = base64.b64encode(self.data).decode("ascii")
            return f"{header};base64,{encoded_data}"
        else:
            encoded_data = quote_from_bytes(self.data)
            return f"{header},{encoded_data}"

    @field_serializer("data", when_used="json")
    def serialize_data(self, data: bytes) -> str:
        """When dumping model in json mode"""
        if self.content_type.find("base64") != -1:
            return base64.b64encode(data).decode("ascii")

        return data.decode(encoding=self.encoding)

    def as_string(self) -> str:
        """Display the data as a string. Bytes are decoded using the `encoding` attribute
        If base64, the data will be re-encoded to base64 bytes then decoded to an ASCII string
        Returns:
            str.
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
        path = self._last_saved_path

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
            logger.exception("Failed to open file %s", path)
            return False
        return True

    def save(self, dest: str | Path) -> None:
        """Copy the file to the specified destination path.
        Updates the filename and the path of the content to reflect the last saved copy.

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
