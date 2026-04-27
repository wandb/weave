from __future__ import annotations

import contextlib
import os
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


def _safe_join(base: str, untrusted_path: str) -> str:
    """Join base and untrusted_path, ensuring the result stays within base.

    Rejects absolute paths, '..' components, and any path that would resolve
    outside of base after symlink resolution.
    """
    if os.path.isabs(untrusted_path):
        raise ValueError(
            f"Path must be relative, got absolute path: {untrusted_path!r}"
        )

    # Normalize to collapse '..' and '.' but don't resolve symlinks yet
    normed = os.path.normpath(untrusted_path)
    if normed.startswith(os.sep):
        raise ValueError(
            f"Path must be relative, got absolute path: {untrusted_path!r}"
        )
    if normed.startswith(".."):
        raise ValueError(f"Path escapes base directory: {untrusted_path!r}")

    joined = os.path.join(base, normed)
    # realpath resolves symlinks; the result must still be under base
    resolved = os.path.realpath(joined)
    real_base = os.path.realpath(base)
    if not resolved.startswith(real_base + os.sep) and resolved != real_base:
        raise ValueError(f"Path escapes base directory: {untrusted_path!r}")

    return joined


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

        # Reuse a single tempdir per artifact so repeat `path()` calls don't
        # orphan a prior TemporaryDirectory whose finalizer fires via GC.
        # `ignore_cleanup_errors` (Python 3.10+) swallows Windows
        # PermissionError when a consumer still holds the file open
        # (e.g. PIL.Image.open, wave.open, VideoFileClip), which otherwise
        # surfaces as PytestUnraisableExceptionWarning during finalization.
        if self.temp_read_dir is None:
            self.temp_read_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        write_path = _safe_join(self.temp_read_dir.name, filename or path)
        os.makedirs(os.path.dirname(write_path), exist_ok=True)
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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            full_path = _safe_join(tmpdir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            yield full_path
            with open(full_path, "rb") as fp:
                self.path_contents[path] = fp.read()
