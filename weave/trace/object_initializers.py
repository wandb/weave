from typing import Any, Protocol


class ObjectInitializer(Protocol):
    """An initializer to ensure saved Weave objects are safe to load back to their original types.

    In many cases, this will be some form of deepcopy to ensure all the data is loaded
    into memory before attempting to return the object.
    """

    def should_initialize(self, obj: Any) -> bool: ...
    def initialize(self, obj: Any) -> None: ...


_object_initializers: list[ObjectInitializer] = []


def register_object_initializer(initializer: ObjectInitializer) -> None:
    _object_initializers.append(initializer)


def initialize_object(obj: Any) -> None:
    for initializer in _object_initializers:
        if initializer.should_initialize(obj):
            initializer.initialize(obj)
            break
