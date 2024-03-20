from typing import Any


class ObjectRecord:
    _class_name: str

    def __init__(self, attrs: dict[str, Any]) -> None:
        for k, v in attrs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f"ObjectRecord({self.__dict__})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ObjectRecord):
            if self._class_name != other._class_name:
                return False
        else:
            if other.__class__.__name__ != getattr(self, "_class_name"):
                return False
        for k, v in self.__dict__.items():
            if k == "_class_name" or k == "id":
                continue
            if getattr(other, k) != v:
                return False
        return True
