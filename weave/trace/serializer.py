"""Pluggable object serializers for Weave

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

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Serializer:
    target_class: type
    save: Callable
    load: Callable

    def id(self) -> str:
        ser_id = self.target_class.__module__ + "." + self.target_class.__name__
        if ser_id.startswith("weave."):
            # Special case for weave.Op (which is current weave.trace.op.Op).
            # The id is just Op, since we've already already stored this as
            # "Op" in the database.
            if ser_id.endswith(".Op"):
                return "Op"
        return self.target_class.__name__


SERIALIZERS = []


def register_serializer(target_class: type, save: Callable, load: Callable) -> None:
    SERIALIZERS.append(Serializer(target_class, save, load))


def get_serializer_by_id(id: str) -> Optional[Serializer]:
    for serializer in SERIALIZERS:
        if serializer.id() == id:
            return serializer
    return None


def get_serializer_for_obj(obj: Any) -> Optional[Serializer]:
    for serializer in SERIALIZERS:
        if isinstance(obj, serializer.target_class):
            return serializer
    return None
