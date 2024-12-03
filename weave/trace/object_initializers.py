from typing import Any, Protocol


class ObjectInitializer(Protocol):
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
