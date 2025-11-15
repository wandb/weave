"""Pluggable object serializers for Weave.

Example:
```
import faiss


from weave.trace import serializer


def save_instance(obj: faiss.Index, artifact, name: str) -> None:
    with artifact.writeable_file_path(f"{name}.faissindex") as write_path:
        faiss.write_index(obj, write_path)


def load_instance(
    artifact,
    name: str,
) -> faiss.Index:
    return faiss.read_index(artifact.path(f"{name}.faissindex"))


serializer.register_serializer(faiss.Index, save_instance, load_instance)
```

After the register_serializer call, if the user tries to save an object
that has a faiss.Index attribute, Weave will store the full FAISS index
instead of just a repr string.

We will also save the load_instance method as an op, and add a reference
to the load op from the saved object, so that the object can be correctly
deserialized in a Python runtime that does not have the serializer
registered.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from typing_extensions import TypeIs

# This is avoiding a circular import.
if TYPE_CHECKING:
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact


SerializeSaveCallable = Callable[[Any, "MemTraceFilesArtifact", str], Any]
SerializeLoadCallable = Callable[["MemTraceFilesArtifact", str, Any], Any]

LegacyInlineLoad = Callable[[Any], Any]
LegacyFileLoad = Callable[["MemTraceFilesArtifact", str], Any]

AllLoadCallables = SerializeLoadCallable | LegacyInlineLoad | LegacyFileLoad


def is_probably_legacy_inline_load(fn: Callable) -> TypeIs[LegacyInlineLoad]:
    """Check if a function is an inline save function."""
    signature = inspect.signature(fn)
    param_count = len(signature.parameters)
    return param_count == 1


def is_probably_legacy_file_load(fn: Callable) -> TypeIs[LegacyFileLoad]:
    """Check if a function is a file load function."""
    signature = inspect.signature(fn)
    param_count = len(signature.parameters)
    return param_count == 2


@dataclass
class Serializer:
    target_class: type
    save: SerializeSaveCallable
    load: SerializeLoadCallable

    # Added to provide a function to check if an object is an instance of the
    # target class because protocol isinstance checks can fail in python3.12+
    instance_check: Callable[[Any], bool] | None = None
    publish_load_op: bool = True

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
    save: SerializeSaveCallable,
    load: SerializeLoadCallable,
    instance_check: Callable[[Any], bool] | None = None,
    publish_load_op: bool = True,
) -> None:
    SERIALIZERS.append(
        Serializer(target_class, save, load, instance_check, publish_load_op)
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
