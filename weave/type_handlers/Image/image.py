"""Defines the custom Image weave type."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from weave.trace import object_preparers
from weave.trace.serialization.protocol import (
    WeaveSerializer,
    SerializationContext,
    DeserializationContext,
    SerializedData,
)

try:
    from PIL import Image
except ImportError:
    dependencies_met = False
else:
    dependencies_met = True

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = "PNG"

class PILImageSerializer(WeaveSerializer[Image.Image]):
    """Serializer for PIL Image objects."""
    
    type_id: ClassVar[str] = "PIL.Image.Image"
    
    @classmethod
    def can_handle(cls, obj: Any) -> bool:
        return isinstance(obj, Image.Image)
    
    def serialize(self, obj: Image.Image, context: SerializationContext) -> SerializedData:
        """Serialize a PIL Image to a file."""
        if context.artifact is None:
            raise ValueError("Cannot serialize PIL Image without an artifact")
            
        fmt = getattr(obj, "format", DEFAULT_FORMAT)
        ext = "png"  # Always use PNG for now
        
        # Note: Using fixed filename as discussed in original comments
        fname = f"image.{ext}"
        with context.artifact.new_file(fname, binary=True) as f:
            obj.save(f, format=DEFAULT_FORMAT)
            
        return SerializedData(
            type_id=self.type_id,
            metadata={"format": fmt},
            content={"filename": fname},
            requires_artifact=True
        )
    
    def deserialize(self, data: SerializedData, context: DeserializationContext) -> Image.Image:
        """Deserialize a PIL Image from a file."""
        if context.artifact is None:
            raise ValueError("Cannot deserialize PIL Image without an artifact")
            
        filename = data.content["filename"]
        if not filename.startswith("image."):
            raise ValueError(f"Expected filename to start with 'image.', got {filename}")
            
        path = context.artifact.path(filename)
        img = Image.open(path)
        
        # This load is necessary to ensure the image is fully loaded
        try:
            img.load()
        except Exception as e:
            logger.exception(f"Failed to load PIL Image: {e}")
            raise
            
        return img

class PILImagePreparer:
    """Prepares PIL Images for serialization."""
    
    def should_prepare(self, obj: Any) -> bool:
        return isinstance(obj, Image.Image)
    
    def prepare(self, obj: Image.Image) -> None:
        try:
            obj.load()
        except Exception as e:
            logger.exception(f"Failed to load PIL Image: {e}")
            raise

def register() -> None:
    """Register the PIL Image serializer and preparer."""
    if dependencies_met:
        from weave.trace.serialization.registry import REGISTRY
        REGISTRY.register(PILImageSerializer)
        object_preparers.register(PILImagePreparer())
