"""Core serialization protocols and types for Weave."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, TypeVar, TYPE_CHECKING, Union

from weave.trace.refs import RefWithExtra
from weave.trace.custom_objs import MemTraceFilesArtifact
if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import TraceServerInterface

T = TypeVar('T')

@dataclass
class SerializationContext:
    """Context for serialization operations."""
    project_id: str
    client: WeaveClient
    ref_chain: List[str]
    artifact: Optional[MemTraceFilesArtifact] = None
    use_dictify: bool = False

@dataclass
class DeserializationContext:
    """Context for deserialization operations."""
    project_id: str
    server: TraceServerInterface
    ref: Optional[RefWithExtra] = None
    artifact: Optional[MemTraceFilesArtifact] = None

@dataclass
class SerializedData:
    """Container for serialized data.
    
    A serializer can either:
    1. Return inline data in the content field
    2. Write to the artifact and return metadata about what was written
    """
    type_id: str
    metadata: dict
    content: Any
    requires_artifact: bool = False

class WeaveSerializer(Protocol[T]):
    """Protocol for Weave serializers.
    
    Each serializer is responsible for handling a specific type or group of types.
    Serializers can either:
    1. Serialize inline to JSON-compatible data structures
    2. Write to files via an artifact
    
    The choice is indicated by requires_artifact in the SerializedData.
    """
    
    @classmethod
    def type_id(cls) -> str:
        """Return the unique identifier for this serializer."""
        ...
    
    @classmethod
    def can_handle(cls, obj: Any) -> bool:
        """Return True if this serializer can handle the given object."""
        ...
    
    def serialize(self, obj: T, context: SerializationContext) -> SerializedData:
        """Serialize an object.
        
        If requires_artifact is True in the returned SerializedData:
        - context.artifact must be provided
        - The serializer should write files to the artifact
        - content can contain metadata about what was written
        
        If requires_artifact is False:
        - content should contain the inline serialized data
        - The artifact will be ignored if provided
        """
        ...
    
    def deserialize(self, data: SerializedData, context: DeserializationContext) -> T:
        """Deserialize data back to an object.
        
        If data.requires_artifact is True:
        - context.artifact must be provided
        - The serializer should read from the artifact using data.content as metadata
        
        If data.requires_artifact is False:
        - The serializer should reconstruct the object from data.content
        - The artifact will be ignored if provided
        """
        ... 