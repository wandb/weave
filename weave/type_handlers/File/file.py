"""Defines the custom File weave type."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import subprocess
import sys
from pathlib import Path

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

logger = logging.getLogger(__name__)


class File:
    """A class representing a file with path, mimetype, and size information."""

    def __init__(self, path: str | Path, mimetype: str | None = None):
        """Initialize a File object.

        Args:
            path: Path to the file (string or pathlib.Path)
            mimetype: Optional MIME type of the file - will be inferred from extension if not provided
        """
        self.path = Path(path) if isinstance(path, str) else path
        self.mimetype = (
            mimetype if mimetype else mimetypes.guess_type(str(self.path))[0]
        )
        self.size = self.path.stat().st_size if self.path.exists() else 0

    def open(self) -> bool:
        """Open the file using the operating system's default application.

        This method uses the platform-specific mechanism to open the file with
        the default application associated with the file's type.

        Returns:
            bool: True if the file was successfully opened, False otherwise.
        """
        try:
            if sys.platform == "win32":
                os.startfile(self.path)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(("open", str(self.path)))
            else:  # linux variants
                subprocess.call(("xdg-open", str(self.path)))
        except Exception as e:
            logger.exception(f"Failed to open file {self.path}: {e}")
            return False
        return True


def save(obj: File, artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("file", binary=True) as f:
        f.write(obj.path.read_bytes())
    metadata = {
        "original_path": str(obj.path),
        "mimetype": obj.mimetype,
        "size": obj.size,
    }
    with artifact.new_file("metadata.json", binary=False) as f:
        json.dump(metadata, f)


def load(artifact: MemTraceFilesArtifact, name: str) -> File:
    metadata_path = artifact.path("metadata.json")
    with open(metadata_path) as f:
        metadata = json.load(f)
    print(metadata)
    path = artifact.path("file")
    return File(path, metadata["mimetype"])


def register() -> None:
    serializer.register_serializer(File, save, load)
