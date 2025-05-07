from pathlib import Path
import os
from typing import Any, TypeVar, Literal, Union, Generic
import re
import base64

SUPPORTED_FORMATS = (
    "mp3",
    "wav",
    "ogg",
    "flac",
    "aac"
)

SupportedFormatType = Literal["mp3", "wav", "ogg", "flac", "aac"]
F = TypeVar("F", bound=SupportedFormatType)

def get_format_from_filename(filename: str) -> SupportedFormatType | None:
    """Get the file format from a filename.
    Args:
        filename: The filename to extract the format from
    Returns:
        The format string or None if no extension is found
    """
    # Get last dot position
    last_dot = filename.rfind(".")

    # If there's no dot or it's the last character, return None
    if last_dot == -1 or last_dot == len(filename) - 1:
        return None
    fmt = filename[last_dot + 1 :].lower()

    if fmt not in SUPPORTED_FORMATS:
        return None

    return fmt

# Case 1: Receive encoded audio data
def is_base64(data: str | bytes | None) -> bool:
    """
    check if a string is base64 encoded.
    """
    if not data:
        return False

    pattern = "^(?:[a-za-z0-9+/]{4})*(?:[a-za-z0-9+/]{2}==|[a-za-z0-9+/]{3}=)?$"

    if isinstance(data, bytes):
        return bool(re.match(pattern.encode(), data))

    return bool(re.match(pattern, data))

class Audio(Generic[F]):
    fmt: SupportedFormatType
    type_param: F
    encoded_data: str

    def __init__(
        self,
        path: Union[str, bytes, Path, os.PathLike, None] = None,
        data: Union[bytes, str, None] = None,
        fmt: Union[SupportedFormatType, None] = None
    ):
        if not path and not (data and fmt):
            raise ValueError("Must provide either path or raw data and format")
        elif data and not fmt:
            raise ValueError("Format is required when passing raw data")

        if path:
            fmt = fmt or get_format_from_filename(str(path))
            if not fmt or fmt.lower() not in SUPPORTED_FORMATS:
                raise ValueError(f"Invalid file path {path}, file must end in one of: mp3, wav, ogg, flac, aac")
            if not os.path.exists(path):
                raise ValueError(f"File {path} does not exist")
            self.encoded_data = base64.b64encode(open(path, "rb").read()).decode('ascii')
            self.fmt = fmt
            return

        elif data and fmt:
            is_encoded = is_base64(data)
            if not is_encoded:
                if isinstance(data, str):
                    bytes_data = data.encode()
                    self.encoded_data = base64.b64encode(bytes_data).decode('ascii')
                    self.fmt = fmt
                    return
                else:
                    self.encoded_data = base64.b64encode(data).decode('ascii')
                    self.fmt = fmt
                    return

def fn(path: str) -> Audio[Literal["mp3"]]:
    return Audio(path)

