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


serializer.register_serializer(Image.Image, ImageSerializer)
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
deserialized in a Python runtimes that don't have the serializer
registered.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Type

from weave.trace.serialization.base_serializer import WeaveSerializer


@dataclass
class Serializer:
    """Internal representation of a registered serializer.

    Stores normalized save/load callables regardless of whether they came from
    a WeaveSerializer class or legacy functions. This keeps usage simple - just
    call serializer.save() or serializer.load().
    """
    target_class: type
    save: Callable
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


SERIALIZERS: list[Serializer] = []


def register_serializer(
    target_class: type,
    save: Callable | Type[WeaveSerializer],
    load: Callable | None = None,
    instance_check: Callable[[Any], bool] | None = None,
) -> None:
    """Register a serializer for a type.

    Accepts either:
    1. A WeaveSerializer class (new API) - pass the class itself, not an instance
    2. Separate save/load functions (legacy API) - provide both functions

    Args:
        target_class: The Python class to register the serializer for
        save: Either a WeaveSerializer class OR a save function
        load: A load function (required if save is a function, omit if save is WeaveSerializer)
        instance_check: Optional function to check if an object is an instance of target_class

    Examples:
        # New API: WeaveSerializer class
        register_serializer(Image.Image, ImageSerializer)

        # Legacy API: separate functions
        register_serializer(faiss.Index, save_fn, load_fn)
    """
    # Normalize to save/load callables at registration time
    if isinstance(save, type) and issubclass(save, WeaveSerializer):
        # New API: extract static methods from the class
        save_func = save.save
        load_func = save.load
    else:
        # Legacy API: use provided functions
        if load is None:
            raise ValueError(
                "When registering function-based serializers, both save and load must be provided"
            )
        save_func = save
        load_func = load

    SERIALIZERS.append(
        Serializer(
            target_class=target_class,
            save=save_func,
            load=load_func,
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
