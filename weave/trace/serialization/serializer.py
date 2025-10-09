"""Pluggable object serializers for Weave.

Register save/load functions for custom types. Supports:
- Inline: save(obj) -> metadata, load(metadata) -> obj
- File-based: save(obj, artifact, name) -> None, load(artifact, name) -> obj
- Hybrid: save(obj, artifact, name) -> metadata, load(artifact, name, metadata) -> obj

Example (Markdown - hybrid pattern):
```python
def save(obj: Markdown, artifact, name: str) -> dict | None:
    with artifact.new_file("content.md", binary=False) as f:
        f.write(obj.markup)
    return {"code_theme": obj.code_theme} if obj.code_theme else None

def load(artifact, name: str, metadata) -> Markdown:
    with artifact.open("content.md", binary=False) as f:
        markup = f.read()
    code_theme = metadata.get("code_theme") if metadata else None
    return Markdown(markup, code_theme=code_theme)

serializer.register_serializer(Markdown, save, load)
```

Load functions are saved as ops for cross-runtime deserialization.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable


def is_inline_save(func: Callable) -> bool:
    """Check if save function is inline (1 param)."""
    return len(inspect.signature(func).parameters) == 1


def is_file_save(func: Callable) -> bool:
    """Check if save function is file-based (3 params)."""
    return len(inspect.signature(func).parameters) == 3


@dataclass
class Serializer:
    """Internal representation of a registered serializer."""
    target_class: type
    save: Callable
    load: Callable
    instance_check: Callable[[Any], bool] | None = None

    def id(self) -> str:
        serializer_id = self.target_class.__module__ + "." + self.target_class.__name__
        # Special case for weave.Op
        if serializer_id.startswith("weave.") and serializer_id.endswith(".Op"):
            return "Op"
        return serializer_id


SERIALIZERS: list[Serializer] = []


def register_serializer(
    target_class: type,
    save: Callable,
    load: Callable,
    instance_check: Callable[[Any], bool] | None = None,
) -> None:
    """Register save/load functions for a type.

    Args:
        target_class: The Python class to serialize
        save: Save function
        load: Load function
        instance_check: Optional isinstance check override

    Examples:
        # File-based with metadata return
        register_serializer(Markdown, save, load)

        # File-based returning None
        register_serializer(Image.Image, save, load)

        # Inline (1 param)
        register_serializer(datetime, save, load)
    """
    SERIALIZERS.append(
        Serializer(
            target_class=target_class,
            save=save,
            load=load,
            instance_check=instance_check,
        )
    )


def get_serializer_by_id(id: str) -> Serializer | None:
    for serializer in SERIALIZERS:
        if serializer.id() == id:
            return serializer
    return None


def get_serializer_for_obj(obj: Any) -> Serializer | None:
    for serializer in SERIALIZERS:
        if serializer.instance_check and serializer.instance_check(obj):
            return serializer
        elif isinstance(obj, serializer.target_class):
            return serializer
    return None
