"""Server-side, client-free copy of weave.type_wrappers.Content.Content.

Only the decode/construction surface the trace server actually uses is kept:
``from_base64``, ``from_data_url``, ``from_url`` and the public fields. The
client SDK keeps the full implementation (ref tracking, save/open, data-URL
emission); this copy is intentionally not shared with it, so the trace server
stays free of client imports.

The pydantic field set is kept byte-identical to the client's Content so that
``model_dump(exclude={"data"})`` produces the same ``metadata.json`` the client
reads back when deserializing a stored Content object (see
weave/type_handlers/Content/content.py).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import Annotated, Any, Generic
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field
from typing_extensions import Self, TypeVar

from weave.trace_server.content.content_types import (
    ContentType,
    ResolvedContentArgs,
)
from weave.trace_server.content.utils import (
    default_filename,
    full_name,
    get_mime_and_extension,
    try_parse_data_url,
)

logger = logging.getLogger(__name__)

# Dummy typevar to allow for passing mimetype/extension through annotated content
# e.x. Content["pdf"] or Content["application/pdf"]
T = TypeVar("T", bound=str)


class Content(BaseModel, Generic[T]):
    """Byte-oriented content with associated metadata.

    Must be instantiated through one of the ``from_*`` classmethods.
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Direct initialization is disabled.
        Please use a classmethod like `Content.from_base64()` to create an instance.
        """
        raise NotImplementedError(
            "Content objects cannot be initialized directly. "
            "Use a classmethod: from_base64, from_data_url, or from_url."
        )

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
        # Use httpx directly (a hard server dependency) rather than the client's
        # weave.utils.http_requests, to keep the trace server free of client
        # imports. Callers gate this on an SSRF check before fetching.
        resp = httpx.get(
            url, headers=headers, timeout=timeout, follow_redirects=True
        )
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
            # Use the response-detected encoding if present, else utf-8
            "encoding": resp.encoding or "utf-8",
        }

        if metadata:
            resolved_args["metadata"] = metadata

        return cls.model_construct(**resolved_args)
