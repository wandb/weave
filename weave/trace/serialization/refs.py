"""Serializers for Weave reference types."""

from __future__ import annotations

from typing import Any, Type, ClassVar

from weave.trace.refs import ObjectRef, TableRef
from weave.trace.serialization.protocol import (
    SerializationContext,
    SerializedData,
    WeaveSerializer,
)

class RefSerializerBase(WeaveSerializer):
    """Base class for reference serializers."""
    
    type_id: ClassVar[str]
    ref_type: ClassVar[Type[Any]]
    
    @classmethod
    def can_handle(cls, obj: Any) -> bool:
        """Check if this serializer can handle the given object."""
        return isinstance(obj, cls.ref_type)
    
    def serialize(self, obj: Any, context: SerializationContext) -> SerializedData:
        """Serialize a reference object."""
        return SerializedData(
            type_id=self.type_id,
            metadata={},
            content=obj.uri()
        )
    
    def deserialize(self, data: SerializedData, context: SerializationContext) -> Any:
        """Deserialize a reference object."""
        uri = data.content
        return self.ref_type.from_uri(uri)

class ObjectRefSerializer(RefSerializerBase):
    """Serializer for ObjectRef instances."""
    type_id = "object_ref"
    ref_type = ObjectRef

class TableRefSerializer(RefSerializerBase):
    """Serializer for TableRef instances."""
    type_id = "table_ref"
    ref_type = TableRef 