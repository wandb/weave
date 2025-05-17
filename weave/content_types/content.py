from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import (
    Generic,
    TypeVar,
)

from weave.content_types.mime_types import guess_mime_type

T = TypeVar("T", bound=str)

# Counterpart for File which allows object creation from bytes in memory
class Content(Generic[T]):
    """A class representing raw data.

    This class handles data storage and provides methods for loading from
    different sources and exporting to files.

    Attributes:
        mime-type: The mime-type of the data
        data: The raw audio data as bytes
        size: The size of the data in bytes

    Args:
        data: The audio data (bytes or base64 encoded string)
        validate_base64: Whether to attempt base64 decoding of the input data

    Raises:
        ValueError: If audio data is empty or format is not supported
    """

    # The preferred file extension to use when saving
    preferred_extension: str

    # File Format
    mime_type: str

    # Raw audio data bytes
    data: bytes

    # Size of the data in bytes
    size: int

    def __init__(
        self,
        data: bytes,
        mime_type: str,
        preferred_extension: str | None = None,
    ) -> None:
        if len(data) == 0:
            raise ValueError("Audio data cannot be empty")

        self.data = data
        self.mime_type = mime_type
        self.size = len(data)

        preferred_extension = preferred_extension or mimetypes.guess_extension(mime_type)
        if not preferred_extension:
            raise ValueError(f"Failed to determine file extension for mime-type: {mime_type}")

        self.preferred_extension = preferred_extension.lstrip(".")

    @classmethod
    def _from_data_with_ext(cls, data: bytes, extension: str) -> Content:
        """Create a Content object from raw data and specified format.

        Args:
            data: Content data as bytes or base64 encoded string
            extension: File extension (e.g., 'wav', 'mp3', 'm4a')

        Returns:
            Audio: A new Audio instance

        Raises:
            ValueError: If format is not supported
        """
        preferred_extension = extension.lower().lstrip(".")
        mime_type = guess_mime_type(kwargs={
            "extension": preferred_extension,
            "buffer": data[:2048]
        })

        if mime_type is None:
            # Not a valid extension - discard it
            preferred_extension = None
            mime_type = guess_mime_type(kwargs={
                "buffer": data[:2048]
            })

        # If we still don't have a mime-type we have to error
        if mime_type is None:
            raise ValueError(
                f"Failed to determine mime-type from file extension: {extension}"
            )

        return cls(
            data=data,
            mime_type=mime_type,
            preferred_extension=extension
        )


    @classmethod
    def from_data(cls, data: bytes, content_type_hint: str | None) -> Content:
        """Create a Content object from raw data and specified format.
        Args:
            data: Content data as bytes
            content_type_hint: Optional MIME type (e.g. application/json) or extension (e.g., 'mp3', json)
        Returns:
            Content: A new Content instance
        Raises:
            ValueError: If format is not supported
        """
        if not content_type_hint:
            mime_type = guess_mime_type(kwargs={"buffer": data[:2048]})
            if not mime_type:
                raise ValueError("Failed to infer mime-type from data - please provide either the format or extension")

            return cls(data, mime_type)

        elif content_type_hint.index("/") != -1:
            # It's a mime-type
            mime_type = content_type_hint
            extension = mimetypes.guess_extension(mime_type)
            if extension is None:
                raise ValueError(f"Failed to determine file extension from mime-type: {mime_type}")
            return cls(data, mime_type, extension)

        return cls._from_data_with_ext(data, content_type_hint)

    @property
    def filename(self) -> str:
        """
        Create a filename based on the mime-type and preferred extension (if available).
        """
        content_type = self.mime_type.split("/")[0]
        extension = self.preferred_extension
        return f"{content_type}.{extension}"

    @property
    def metadata(self) -> dict[str, str | int]:
        return {
            "size": self.size,
            "mime_type": self.mime_type,
        }

    def save(self, path: str | Path) -> None:
        """Export audio data to a file.

        Args:
            path: Path where the audio file should be written
        """
        with open(path, "wb") as f:
            f.write(self.data)
