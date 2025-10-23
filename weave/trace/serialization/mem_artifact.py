from __future__ import annotations

import contextlib
import os
import shutil
import sys
import tempfile
from collections.abc import Generator, Iterator, Mapping
from io import BytesIO, StringIO
from typing import Literal, overload

from weave.trace.serialization import (
    op_type,  # noqa: F401, Must import this to register op save/load
)

# This uses the older weave query_service's Artifact interface. We could
# probably simplify a lot at this point by removing the internal requirement
# to use this interface.


def _windows_safe_rmtree(path: str, retries: int = 3) -> None:
    """Remove a directory tree with Windows-safe error handling.

    On Windows, file handles may not be released immediately even after
    closing files. This function retries the removal operation to handle
    transient permission errors that occur on Windows.

    Args:
        path: Path to directory to remove
        retries: Number of times to retry on permission errors
    """
    import time

    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except (PermissionError, OSError) as e:
            if attempt == retries - 1:
                # On the final attempt, ignore the error on Windows
                # since these are finalization warnings, not critical failures
                if sys.platform == "win32":
                    return
                raise
            # Wait briefly before retrying to allow file handles to be released
            time.sleep(0.1)


class MemTraceFilesArtifact:
    temp_read_dir: tempfile.TemporaryDirectory | None
    path_contents: dict[str, bytes]

    def __init__(
        self,
        path_contents: Mapping[str, str | bytes] | None = None,
        metadata: dict[str, str] | None = None,
    ):
        if path_contents is None:
            path_contents = {}
        self.path_contents = path_contents  # type: ignore
        if metadata is None:
            metadata = {}
        self._metadata = metadata
        self.temp_read_dir = None

    def __del__(self) -> None:
        """Clean up temporary directory with Windows-safe error handling."""
        if self.temp_read_dir is not None:
            try:
                # Since we used delete=False, we need to manually clean up
                _windows_safe_rmtree(self.temp_read_dir.name)
            except Exception:
                # Ignore all errors during finalization
                pass

    @overload
    @contextlib.contextmanager
    def new_file(
        self, path: str, binary: Literal[False] = False
    ) -> Iterator[StringIO]: ...

    @overload
    @contextlib.contextmanager
    def new_file(self, path: str, binary: Literal[True]) -> Iterator[BytesIO]: ...

    @contextlib.contextmanager
    def new_file(self, path: str, binary: bool = False) -> Iterator[StringIO | BytesIO]:
        f: StringIO | BytesIO
        if binary:
            f = BytesIO()
        else:
            f = StringIO()
        yield f
        self.path_contents[path] = f.getvalue()  # type: ignore
        f.close()

    @property
    def is_saved(self) -> bool:
        return True

    @contextlib.contextmanager
    def open(self, path: str, binary: bool = False) -> Iterator[StringIO | BytesIO]:
        f: StringIO | BytesIO
        try:
            if binary:
                val = self.path_contents[path]
                if not isinstance(val, bytes):
                    raise ValueError(
                        f"Expected binary file, but got string for path {path}"
                    )
                f = BytesIO(val)
            else:
                val = self.path_contents[path]
                f = StringIO(val.decode("utf-8"))
        except KeyError:
            raise FileNotFoundError(path) from None
        yield f
        f.close()

    def path(self, path: str, filename: str | None = None) -> str:
        if path not in self.path_contents:
            raise FileNotFoundError(path)

        # Use delete=False to prevent automatic cleanup that fails on Windows
        # We handle cleanup manually in __del__ with proper error handling
        self.temp_read_dir = tempfile.TemporaryDirectory(delete=False)
        write_path = os.path.join(self.temp_read_dir.name, filename or path)
        with open(write_path, "wb") as f:
            f.write(self.path_contents[path])
            f.flush()
            os.fsync(f.fileno())
        return write_path

    # @property
    # def metadata(self) -> artifact_fs.ArtifactMetadata:
    #     return artifact_fs.ArtifactMetadata(self._metadata, {**self._metadata})

    @contextlib.contextmanager
    def writeable_file_path(self, path: str) -> Generator[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            full_path = os.path.join(tmpdir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            yield full_path
            with open(full_path, "rb") as fp:
                self.path_contents[path] = fp.read()
