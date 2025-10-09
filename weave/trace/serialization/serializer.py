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


serializer.register_weave_serializer(Image.Image, ImageSerializer)
```

## Legacy Function-Based API (Still Supported)

```python
from weave.trace import serializer


def save_instance(obj: faiss.Index, artifact, name: str) -> None:
    with artifact.writeable_file_path(f"{name}.faissindex") as write_path:
        faiss.write_index(obj, write_path)


def load_instance(artifact, name: str) -> faiss.Index:
    return faiss.read_index(artifact.path(f"{name}.faissindex"))


serializer.register_serializer_functions(faiss.Index, save_instance, load_instance)
```

After registering a serializer, if the user tries to save an object
that has the registered type, Weave will use the custom serializer
instead of just storing a repr string.

We will also save the load_instance method as an op, and add a reference
to the load op from the saved object, so that the object can be correctly
deserialized in a Python runtimes that don't have the serializer
registered.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Type

from typing_extensions import TypeIs

from weave.trace.serialization.base_serializer import WeaveSerializer

# Type for legacy inline save functions
InlineSave = Callable[[Any], Any]
if TYPE_CHECKING:
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact

# Type for legacy file save functions
FileSave = Callable[[Any, "MemTraceFilesArtifact", str], None]


def is_inline_save(value: Callable) -> TypeIs[InlineSave]:
    """Check if a value is an inline save function (legacy API only)."""
    signature = inspect.signature(value)
    param_count = len(signature.parameters)
    return param_count == 1


def is_file_save(value: Callable) -> TypeIs[FileSave]:
    """Check if a value is a file-based save function (legacy API only)."""
    signature = inspect.signature(value)
    params = list(signature.parameters.values())
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
    """Internal representation of a registered serializer.

    This can represent either:
    - A WeaveSerializer class (new API)
    - A pair of save/load functions (legacy API)
    """
    target_class: type

    # For new API: this is the WeaveSerializer class itself
    # For legacy API: this is the save function
    weave_serializer: Type[WeaveSerializer] | None = None
    legacy_save: Callable | None = None
    legacy_load: Callable | None = None

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

    def is_weave_serializer(self) -> bool:
        """Check if this is a WeaveSerializer (new API) vs legacy functions."""
        return self.weave_serializer is not None

    def get_save_func(self) -> Callable:
        """Get the save function/method for this serializer."""
        if self.weave_serializer:
            return self.weave_serializer.save
        return self.legacy_save  # type: ignore

    def get_load_func(self) -> Callable:
        """Get the load function/method for this serializer."""
        if self.weave_serializer:
            return self.weave_serializer.load
        return self.legacy_load  # type: ignore


SERIALIZERS: list[Serializer] = []


def register_weave_serializer(
    target_class: type,
    serializer_class: Type[WeaveSerializer],
    instance_check: Callable[[Any], bool] | None = None,
) -> None:
    """Register a WeaveSerializer for a type (new API).

    Args:
        target_class: The Python class to register the serializer for
        serializer_class: The WeaveSerializer class (not an instance!)
        instance_check: Optional function to check if an object is an instance of target_class

    Example:
        register_weave_serializer(Image.Image, ImageSerializer)
    """
    SERIALIZERS.append(
        Serializer(
            target_class=target_class,
            weave_serializer=serializer_class,
            instance_check=instance_check,
        )
    )


def register_serializer_functions(
    target_class: type,
    save: Callable,
    load: Callable,
    instance_check: Callable[[Any], bool] | None = None,
) -> None:
    """Register save/load functions for a type (legacy API).

    Args:
        target_class: The Python class to register the serializer for
        save: The save function
        load: The load function
        instance_check: Optional function to check if an object is an instance of target_class

    Example:
        register_serializer_functions(faiss.Index, save_instance, load_instance)
    """
    SERIALIZERS.append(
        Serializer(
            target_class=target_class,
            legacy_save=save,
            legacy_load=load,
            instance_check=instance_check,
        )
    )


# Legacy API for backward compatibility
def register_serializer(
    target_class: type,
    save: Callable | Type[WeaveSerializer],
    load: Callable | None = None,
    instance_check: Callable[[Any], bool] | None = None,
) -> None:
    """Register a serializer for a type (legacy overloaded API).

    This function is maintained for backward compatibility but the specific
    functions register_weave_serializer() and register_serializer_functions()
    are preferred for clarity.

    Args:
        target_class: The Python class to register the serializer for
        save: Either a WeaveSerializer class OR a save function
        load: A load function (required if save is a function, must be None if save is WeaveSerializer)
        instance_check: Optional function to check if an object is an instance of target_class
    """
    # Try to determine if save is a WeaveSerializer class
    if isinstance(save, type) and issubclass(save, WeaveSerializer):
        register_weave_serializer(target_class, save, instance_check)
    else:
        # Legacy function-based API
        if load is None:
            raise ValueError(
                "When using function-based serialization, both save and load must be provided"
            )
        register_serializer_functions(target_class, save, load, instance_check)


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
