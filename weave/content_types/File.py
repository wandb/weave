"""Defines the custom File weave type."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

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
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} does not exist")
        if not self.path.is_file():
            raise FileNotFoundError(f"{self.path} is not a file")
        mimetype = mimetype if mimetype else mimetypes.guess_type(str(self.path))[0]
        if mimetype is None:
            raise ValueError(f"Could not determine MIME type for {self.path} - provide it manually")
        self.mimetype = mimetype
        self.size = self.path.stat().st_size

    @property
    def filename(self) -> str:
        """Get the filename of the file.

        Returns:
            str: The name of the file without the directory path.
        """
        return self.path.name

    @property
    def metadata(self) -> dict[str, str | int]:
        return {
            "size": self.size,
            "mime_type": self.mimetype,
            "original_path": self.filename # For compatibility with File metadata
        }

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

    def save(self, dest: str | Path) -> None:
        """Copy the file to the specified destination path.

        Args:
            dest: Destination path where the file will be copied to (string or pathlib.Path)
                  The destination path can be a file or a directory.
        """
        path = Path(dest) if isinstance(dest, str) else dest
        os.makedirs(path.parent, exist_ok=True)
        shutil.copy2(self.path, path)
