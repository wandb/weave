"""Base class for Weave serialization.

This module defines the unified serialization interface that all custom type
serializers should implement. It replaces the previous inspection-based approach
with an explicit serializer base class that supports both files and metadata.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact


class WeaveSerializer(ABC):
    """Base class for all Weave serializers.

    Serializers handle converting custom Python objects to a format that can be
    stored in the Weave trace server, and reconstructing those objects later.

    IMPORTANT: Both save() and load() are static methods because they don't need
    instance state. The load function gets serialized as an op, allowing
    deserialization in Python runtimes that don't have the serializer registered.

    This unified interface supports three serialization patterns:
    1. Metadata-only: Return data from save(), use it in load()
    2. Files-only: Write to artifact, return None from save()
    3. Hybrid: Write to artifact AND return metadata

    The implementation is entirely up to the subclass - callers don't need to
    know which pattern is used.

    Example (Metadata-only):
        ```python
        class DateTimeSerializer(WeaveSerializer):
            @staticmethod
            def save(obj: datetime, artifact, name: str) -> dict:
                return {"iso": obj.isoformat()}

            @staticmethod
            def load(artifact, name: str, metadata: dict) -> datetime:
                return datetime.fromisoformat(metadata["iso"])
        ```

    Example (Files-only):
        ```python
        class ImageSerializer(WeaveSerializer):
            @staticmethod
            def save(obj: Image.Image, artifact, name: str) -> None:
                with artifact.new_file("image.png", binary=True) as f:
                    obj.save(f, format="PNG")
                return None

            @staticmethod
            def load(artifact, name: str, metadata: Any) -> Image.Image:
                filename = next(iter(artifact.path_contents))
                return Image.open(artifact.path(filename))
        ```

    Example (Hybrid - files + metadata):
        ```python
        class AudioSerializer(WeaveSerializer):
            @staticmethod
            def save(obj: Audio, artifact, name: str) -> dict:
                # Save audio file
                with artifact.new_file(f"audio.{obj.format}", binary=True) as f:
                    f.write(obj.data)
                # Return metadata
                return {"format": obj.format, "duration": obj.duration}

            @staticmethod
            def load(artifact, name: str, metadata: dict) -> Audio:
                # Use both files and metadata
                audio_file = artifact.path(f"audio.{metadata['format']}")
                return Audio.from_path(audio_file)
        ```
    """

    @staticmethod
    def save(obj: Any, artifact: "MemTraceFilesArtifact", name: str) -> Any | None:
        """Save an object, optionally returning metadata.

        Args:
            obj: The object to serialize
            artifact: The artifact to save files to (if needed)
            name: A name hint for the object (may be used in filenames)

        Returns:
            Optional metadata (dict, string, etc.) or None if only using files.
            The metadata must be JSON-serializable.
        """
        raise NotImplementedError("Subclasses must implement save()")

    @staticmethod
    def load(
        artifact: "MemTraceFilesArtifact", name: str, metadata: Any | None
    ) -> Any:
        """Load an object from files and/or metadata.

        This function will be serialized as an op, so it must be a static method.

        Args:
            artifact: The artifact containing files (may be empty)
            name: A name hint for the object
            metadata: The metadata returned from save(), or None

        Returns:
            The deserialized object
        """
        raise NotImplementedError("Subclasses must implement load()")
