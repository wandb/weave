from __future__ import annotations

import base64
import binascii
import mimetypes
from pathlib import Path
from typing import (
    Generic,
    TypeVar,
)

from weave.content_types.File import File
from weave.content_types.content import Content
from weave.content_types.mime_types import guess_mime_type

def handle_content_type_hint(content_type_hint: str | None) -> dict[str, str]:
    result = {}
    if not content_type_hint:
        return {}

    elif content_type_hint.index("/") != -1:
        # It's a mime-type
        result["mime_type"] = content_type_hint
        result["extension"] = mimetypes.guess_extension(content_type_hint)
    else:
        # It's an extension
        result["extension"] = content_type_hint
        result["mime_type"] = mimetypes.guess_type(content_type_hint)[0]

    return result

def try_decode(data: str | bytes) -> str | bytes:
    """Attempt to decode data as base64 or convert to bytes.

    This function tries to decode the input as base64 first. If that fails,
    it will return the data as bytes, converting if needed.

    Args:
        data: Input data as string or bytes, potentially base64 encoded

    Returns:
        bytes: The decoded data as bytes
    """
    try:
        return base64.b64decode(data, validate=True)
    except binascii.Error:
        return data

class WeaveObject:
    file_or_content: File | Content

    def __init__(self, val: str | bytes | Path, content_type_hint: str | None = None):
        import os
        parsed_content_type = handle_content_type_hint(content_type_hint)

        if isinstance(val, str | Path) and os.path.isfile(val):
            self.file_or_content = File(val, parsed_content_type['mime_type'])
            return

        elif isinstance(val, Path):
            raise ValueError(f"File at path {val} does not exist")

        # If we get here, val is either a base64 string or raw bytes
        elif isinstance(val, str):
            val = try_decode(val)

        if not isinstance(val, bytes):
            raise ValueError("Object value must be a path, base64 string, or bytes")

        elif len(parsed_content_type) != 2:
            # It's not a path - make sure we got both mime and extension, if not, try to get it from the data
            # It's ok if this throws Content would have to do the same thing anyways and it would just throw later
            mime_type = guess_mime_type(kwargs={"buffer": val[:2048]})

            # Decoding was successful, delegate to Content
            self.file_or_content = Content.from_data(val, mime_type)

        # We have the mime-type, bytes, and extension, so we can create the Content object directly
        self.file_or_content = Content(
            data=val,
            mime_type=parsed_content_type['mime_type'],
            preferred_extension=parsed_content_type['extension']
        )
