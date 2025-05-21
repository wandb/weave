from pathlib import Path
import subprocess
import logging
logger = logging.getLogger(__name__)
import threading
from hashlib import sha256
import base64
from typing import TypedDict
from .mime_resolver import guess_extension, guess_mime_type

class ContentMetadata(TypedDict):
    mimetype: str
    extension: str
    filename: str
    size: int
    original_path: str | None
    pyclass: str

class ContentArgs(TypedDict):
    input: str | Path | bytes
    mimetype: str | None
    extension: str | None

class ContentProperties(ContentMetadata):
    data: bytes

def normalize_file_args(input: Path, mimetype: str | None=None, extension: str | None=None) -> ContentProperties:
    buffer = input.read_bytes()[:2048]

    mimetype = mimetype or guess_mime_type(
        buffer=buffer[:2048],
        mimetype=mimetype,
        extension=extension,
    )

    if mimetype is None:
        raise ValueError("MIME type could not be determined from input data.")

    extension = extension or guess_extension(mimetype)

    if not isinstance(extension, str):
        raise ValueError(f"File Extension could not be determined mime-type {mimetype}.")

    data: bytes = input.read_bytes()

    return {
        "data": data,
        "mimetype": mimetype,
        "extension": extension,
        "filename": input.name,
        "original_path": str(input),
        "size": input.stat().st_size,
        "pyclass": "Content",
    }


def normalize_bytes_args(input: bytes, mimetype: str | None=None, extension: str | None=None) -> ContentProperties:
    mimetype = mimetype or guess_mime_type(
        buffer=input[:2048],
        mimetype=mimetype,
        extension=extension,
    )

    if mimetype is None:
        raise ValueError("MIME type could not be determined from input data.")

    extension = extension or guess_extension(mimetype)

    if not isinstance(extension, str):
        raise ValueError(f"File Extension could not be determined mime-type {mimetype}.")
    sha256_hash = sha256(input).hexdigest()
    filename = f"{sha256_hash[:8]}.{extension}"

    return {
        "data": input,
        "mimetype": mimetype,
        "extension": extension,
        "filename": filename,
        "original_path": None,
        "size": len(input),
        "pyclass": "Content",
    }

def normalize_base64_args(input: str, mimetype: str | None=None, extension: str | None=None) -> ContentProperties:
    try:
        data = base64.b64decode(input)
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}")
    return normalize_bytes_args(data, mimetype, extension)

def is_valid_path(input: str | Path) -> bool:
    if isinstance(input, str):
        input = Path(input)
    return input.exists() and input.is_file()

def normalize_args(
    input: bytes | str | Path,
    mimetype=None,
    extension=None
) -> ContentProperties:
    if isinstance(input, Path):
        return normalize_file_args(input, mimetype, extension)
    elif isinstance(input, bytes):
        return normalize_bytes_args(input, mimetype, extension)

    # Here we know it's a string
    if is_valid_path(input):
        return normalize_file_args(Path(input), mimetype, extension)

    # Only option left is base64
    try:
        return normalize_base64_args(input, mimetype, extension)

    except ValueError:
        raise ValueError(f"Failed to determine input type")

# Currently unused, will be useful when opening from a tempfile is implemented for non-file Content
def popen_and_call(on_exit, popen_args):
    """
    Runs the given args in a subprocess.Popen, and then calls the function
    on_exit when the subprocess completes.
    on_exit is a callable object, and popen_args is a list/tuple of args that 
    would give to subprocess.Popen.
    """
    def run_in_thread(on_exit, popen_args):
        proc = subprocess.Popen(*popen_args)
        proc.wait()
        on_exit()
        return

    thread = threading.Thread(target=run_in_thread, args=(on_exit, popen_args))
    thread.start()
    # returns immediately after the thread starts
    return thread

