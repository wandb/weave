from typing import Callable, Any, Optional
from dataclasses import dataclass


@dataclass
class Serializer:
    target_class: type
    save: Callable
    load: Callable

    def id(self) -> str:
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
