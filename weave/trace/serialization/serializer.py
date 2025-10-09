"""Pluggable object serializers for Weave.

This module provides a unified serialization system for custom Python objects.
You can use either the new class-based API or the legacy function-based API.

## New Class-Based API (Recommended)

```python
from weave.trace.serialization.base_serializer import WeaveSerializer
from weave.trace.serialization import serializer
from PIL import Image


class ImageSerializer(WeaveSerializer):
    @staticmethod
    def save(obj: Image.Image, artifact, name: str) -> None:
        with artifact.new_file("image.png", binary=True) as f:
            obj.save(f, format="PNG")
        return None  # Files-only, no metadata

    @staticmethod
    def load(artifact, name: str, metadata) -> Image.Image:
        return Image.open(artifact.path("image.png"))


serializer.register_serializer(Image.Image, ImageSerializer())
```

## Legacy Function-Based API (Still Supported)

```python
from weave.trace import serializer


def save_instance(obj: faiss.Index, artifact, name: str) -> None:
    with artifact.writeable_file_path(f"{name}.faissindex") as write_path:
        faiss.write_index(obj, write_path)


def load_instance(artifact, name: str) -> faiss.Index:
    return faiss.read_index(artifact.path(f"{name}.faissindex"))


serializer.register_serializer(faiss.Index, save_instance, load_instance)
```

After registering a serializer, if the user tries to save an object
that has the registered type, Weave will use the custom serializer
instead of just storing a repr string.

We will also save the load_instance method as an op, and add a reference
to the load op from the saved object, so that the object can be correctly
deserialized in a Python runtime that does not have the serializer
registered.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Union

from typing_extensions import TypeIs

from weave.trace.serialization.base_serializer import WeaveSerializer

# Not locking down the return type for inline encoding but
# it would be expected to be something like a str or dict.
InlineSave = Callable[[Any], Any]
# This is avoiding a circular import.
if TYPE_CHECKING:
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact

FileSave = Callable[[Any, "MemTraceFilesArtifact", str], None]
Save = Union[InlineSave, FileSave, WeaveSerializer]


def is_inline_save(value: Callable | WeaveSerializer) -> TypeIs[InlineSave]:
    """Check if a value is an inline save function (legacy API only).

    New WeaveSerializer instances are never considered inline since they
    handle both files and metadata through a unified interface.
    """
    if isinstance(value, WeaveSerializer):
        return False
    signature = inspect.signature(value)
    param_count = len(signature.parameters)
    return param_count == 1


def is_file_save(value: Callable | WeaveSerializer) -> TypeIs[FileSave]:
    """Check if a value is a file-based save function (legacy API only).

    New WeaveSerializer instances are never considered file-only since they
    handle both files and metadata through a unified interface.
    """
    if isinstance(value, WeaveSerializer):
        return False
    signature = inspect.signature(value)
    params = list(signature.parameters.values())
    # Check parameter count and return type without relying on annotations
    # that would cause circular import
    if len(params) != 3:
        return False
    name_annotation = params[2].annotation
    return (
        (
            name_annotation is str
            or name_annotation == "str"
            or name_annotation == inspect._empty
        )
        and (
            signature.return_annotation is None
            or signature.return_annotation == "None"
            or signature.return_annotation == inspect._empty
        )
    )


@dataclass
class Serializer:
    target_class: type
    save: Save
    load: Callable

    # Added to provide a function to check if an object is an instance of the
    # target class because protocol isinstance checks can fail in python3.12+
    instance_check: Callable[[Any], bool] | None = None

    def id(self) -> str:
        serializer_id = self.target_class.__module__ + "." + self.target_class.__name__
        # Special case for weave.Op (which is currently weave.trace.op.Op).
        # The id is just Op, since we've already stored this as
        # "Op" in the database.
        if serializer_id.startswith("weave.") and serializer_id.endswith(".Op"):
            return "Op"
        return serializer_id


SERIALIZERS = []


def register_serializer(
    target_class: type,
    save: Callable | WeaveSerializer,
    load: Callable | None = None,
    instance_check: Callable[[Any], bool] | None = None,
) -> None:
    """Register a serializer for a type.

    Args:
        target_class: The Python class to register the serializer for
        save: Either a WeaveSerializer instance (new API), or a save function (legacy API)
        load: A load function (required for legacy API, ignored for new API)
        instance_check: Optional function to check if an object is an instance of target_class
    """
    # New API: save is a WeaveSerializer instance
    if isinstance(save, WeaveSerializer):
        if load is not None:
            raise ValueError(
                "When using a WeaveSerializer, the load parameter should not be provided. "
                "The load static method is accessed from the class."
            )
        # Access the static load method from the class
        load_fn = save.load
        SERIALIZERS.append(
            Serializer(
                target_class=target_class,
                save=save,
                load=load_fn,  # Store the static load method
                instance_check=instance_check,
            )
        )
    # Legacy API: save and load are separate functions
    else:
        if load is None:
            raise ValueError(
                "When using function-based serialization, both save and load must be provided"
            )
        SERIALIZERS.append(Serializer(target_class, save, load, instance_check))


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
