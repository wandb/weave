"""Serialization handlers for image types."""

from __future__ import annotations

import logging
from typing import Any

from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.registry import SerializationContext, register
from weave.utils.invertable_dict import InvertableDict

logger = logging.getLogger(__name__)

# Try to import PIL
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

DEFAULT_FORMAT = "PNG"

pil_format_to_ext = InvertableDict[str, str](
    {
        "JPEG": "jpg",
        "PNG": "png",
        "WEBP": "webp",
    }
)
ext_to_pil_format = pil_format_to_ext.inv


def serialize_pil_image(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a PIL Image."""
    if not PIL_AVAILABLE:
        return {"_type": "FallbackString", "_value": str(obj)}
    
    # Create artifact for file storage
    artifact = MemTraceFilesArtifact()
    
    # Get image format
    fmt = getattr(obj, "format", DEFAULT_FORMAT)
    ext = pil_format_to_ext.get(fmt)
    if ext is None:
        logger.debug(f"Unknown image format {fmt}, defaulting to {DEFAULT_FORMAT}")
        ext = pil_format_to_ext[DEFAULT_FORMAT]
    
    # Save image to artifact
    fname = f"image.{ext}"
    with artifact.new_file(fname, binary=True) as f:
        obj.save(f, format=ext_to_pil_format[ext])
    
    # Get encoded files
    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)
        for k, v in artifact.path_contents.items()
    }
    
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "PIL.Image.Image"},
        "files": encoded_path_contents,
    }
    
    return result


def deserialize_pil_image(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize a PIL Image."""
    if not PIL_AVAILABLE:
        return None
    
    if data.get("_type") != "CustomWeaveType":
        return None
    
    if data.get("weave_type", {}).get("type") != "PIL.Image.Image":
        return None
    
    # Reconstruct artifact from files
    files = data.get("files", {})
    artifact = MemTraceFilesArtifact(files, metadata={})
    
    # Load image
    filename = next(iter(artifact.path_contents))
    if not filename.startswith("image."):
        raise ValueError(f"Expected filename to start with 'image.', got {filename}")
    
    path = artifact.path(filename)
    return Image.open(path)


def is_pil_image(obj: Any) -> bool:
    """Check if object is a PIL Image."""
    if not PIL_AVAILABLE:
        return False
    return isinstance(obj, Image.Image)


def register_image_handlers():
    """Register all image-related serialization handlers."""
    if PIL_AVAILABLE:
        register(
            Image.Image,
            serialize_pil_image,
            deserialize_pil_image,
            priority=75,
            check_func=is_pil_image
        )