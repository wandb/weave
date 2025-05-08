import base64
import os
import re
from pathlib import Path
from typing import (
    Generic,
    Literal,
    TypeVar,
    Union,
    get_args,
)

SupportedFormatType = Literal["mp3", "wav"]


def get_format_from_filename(filename: str) -> Union[str, None]:
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

    if not fmt in get_args(SupportedFormatType):
        return None

    return fmt


def is_base64(data: Union[str, bytes, None]) -> bool:
    # check if a string is base64 encoded.
    if not data:
        return False

    pattern = "^(?:[a-za-z0-9+/]{4})*(?:[a-za-z0-9+/]{2}==|[a-za-z0-9+/]{3}=)?$"

    if isinstance(data, bytes):
        return bool(re.match(pattern.encode(), data))

    return bool(re.match(pattern, data))


F = TypeVar("F", bound=SupportedFormatType)


class Audio(Generic[F]):
    """
    Audio class to handle audio data.
    Can be initialized with a file path or raw audio data with a format

    Direct initialization in Op pre or post-process function:

    From a file with ext:
    weave.Audio(path='some_file.mp3')

    Filename without ext + format:
    weave.Audio(path='some_file', fmt='mp3')

    Base64 encoded bytes (Like what LLM generations return) + format:
    weave.Audio(data=base64_str_or_bytes, fmt='mp3')

    Raw decoded audio bytes + format:
    with open('some_file.mp3', 'rb') as f:
        raw_audio_bytes = f.read()
    weave.Audio(data=raw_audio_bytes, fmt='mp3')


    Annotated initialization performed by SDK:

    def read_example(path_to_mp3: str) -> Annotated[str, weave.Audio]:
        return path_to_mp3

    def read_example(path_to_mp3: str) -> Annotated[bytes, weave.Audio[Literal["mp3"]]]:
        with open(path_to_mp3, "rb") as f:
            raw_audio_bytes = f.read()
        return raw_audio_bytes

    def gen_audio(prompt: str) -> Annotated[str, weave.Audio[Literal["mp3"]]]:
        completion = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "mp3"},
            messages=[
                {
                    "role": "user",
                    "content": "Is a golden retriever a good family dog?"
                }
            ]
        )

        return completion.choices[0].message.audio.data
    """

    # File Format
    fmt: str

    # Base64 encoded audio data
    data: str

    def __init__(
        self,
        path: Union[str, bytes, Path, os.PathLike, None] = None,
        data: Union[bytes, str, None] = None,
        fmt: Union[F, None] = None,
    ):
        if not path and not (data and fmt):
            raise ValueError("Must provide either path or raw data and format")
        elif data and not fmt:
            raise ValueError("Format is required when passing raw data")

        if path:
            if isinstance(path, bytes):
                path = path.decode()
            fmt_str = fmt or get_format_from_filename(str(path))

            if not fmt_str or fmt_str.lower() not in get_args(SupportedFormatType):
                raise ValueError(
                    f"Invalid file path {path}, file must end in one of: mp3 or wav"
                )
            if not os.path.exists(path):
                raise ValueError(f"File {path} does not exist")
            self.data = base64.b64encode(open(path, "rb").read()).decode("ascii")
            self.fmt = fmt_str
            return

        elif data and fmt:
            # Case 1: Receive encoded audio data
            is_encoded = is_base64(data)

            # Case 2: Receive raw audio data
            if not is_encoded:
                if isinstance(data, str):
                    bytes_data = data.encode()
                    self.data = base64.b64encode(bytes_data).decode("ascii")
                    self.fmt = fmt
                    return
                else:
                    self.data = base64.b64encode(data).decode("ascii")
                    self.fmt = fmt
                    return

    def export(self, path: Union[str, bytes, Path, os.PathLike]) -> None:
        with open(path, "wb") as f:
            f.write(base64.b64decode(self.data))
