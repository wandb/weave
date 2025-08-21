"""Protocols for serialization in Weave.

This module defines the protocols and interfaces that objects can implement
to customize their serialization behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from typing_extensions import Self


@runtime_checkable
class Serializable(Protocol):
    """Protocol for objects that can be serialized to and from Weave format."""

    def __weave_serialize__(self) -> dict[str, Any]:
        """Serialize the object to a dictionary representation.
        
        Returns:
            A dictionary that can be JSON-serialized containing all necessary
            data to reconstruct the object.
        """
        ...

    @classmethod
    def __weave_deserialize__(cls, data: dict[str, Any]) -> Self:
        """Deserialize the object from a dictionary representation.
        
        Args:
            data: The dictionary representation of the object.
            
        Returns:
            A new instance of the class reconstructed from the data.
        """
        ...


@runtime_checkable
class FileSerializable(Protocol):
    """Protocol for objects that require file-based serialization."""

    def __weave_save_files__(self, artifact: Any, name: str) -> dict[str, Any]:
        """Save the object's data to files and return metadata.
        
        Args:
            artifact: The artifact to write files to.
            name: The base name for files.
            
        Returns:
            Metadata dictionary describing the saved files.
        """
        ...

    @classmethod
    def __weave_load_files__(cls, artifact: Any, name: str, metadata: dict[str, Any]) -> Self:
        """Load the object from files.
        
        Args:
            artifact: The artifact to read files from.
            name: The base name for files.
            metadata: Metadata about the saved files.
            
        Returns:
            A new instance of the class reconstructed from the files.
        """
        ...