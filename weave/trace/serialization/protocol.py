"""Core serialization protocols and types for Weave."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, TypeVar, TYPE_CHECKING

from weave.trace.refs import RefWithExtra
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
    use_dictify: bool = False

@dataclass
class DeserializationContext:
    """Context for deserialization operations."""
    project_id: str
    server: TraceServerInterface
    ref: Optional[RefWithExtra] = None

@dataclass
class SerializedData:
    """Container for serialized data."""
    type_id: str
    metadata: dict
    content: Any

class WeaveSerializer(Protocol[T]):
    """Protocol for Weave serializers.
    
    Each serializer is responsible for handling a specific type or group of types.
    Serializers can be registered with the SerializerRegistry to handle those types.
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
        """Serialize an object to SerializedData."""
        ...
    
    def deserialize(self, data: SerializedData, context: DeserializationContext) -> T:
        """Deserialize SerializedData back to an object."""
        ... 