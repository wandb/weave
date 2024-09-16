"""A Placeholder is a token in a prompt that is replaced with a value at runtime."""

from typing import Any, Optional


class Placeholder:
    # TODO: Limit type values
    # TODO: Add other options based on type, e.g. choices
    name: str
    type: str
    default: Optional[str]

    def __init__(
        self, name: str, type: Optional[str] = None, default: Optional[str] = None
    ):
        self.name = name
        self.type = type or "string"
        self.default = default

    def copy(self) -> "Placeholder":
        """Create a deep copy of the Placeholder object."""
        return Placeholder(name=self.name, type=self.type, default=self.default)

    def __str__(self) -> str:
        return self.as_str()

    def as_str(self) -> str:
        result = self.name
        if self.type != "string":
            result += f" type:{self.type}"
        if self.default is not None:
            result += f" default:{self.default}"
        return "{" + result + "}"

    def as_rich_str(self) -> str:
        return f"[orange3]{self}[/]"

    def to_json(self) -> dict[str, Any]:
        json_dict: dict[str, str] = {"name": self.name, "type": self.type}
        if self.default is not None:
            json_dict["default"] = self.default
        return json_dict

    def __repr__(self) -> str:
        repr_str = f"Placeholder(name='{self.name}', type='{self.type}'"
        if self.default is not None:
            repr_str += f", default='{self.default}'"
        repr_str += ")"
        return repr_str

    @staticmethod
    def from_str(s: str) -> "Placeholder":
        s = s.lstrip("{").rstrip("}")
        parts = s.split()
        name = parts[0]
        type = None
        default = None

        for part in parts[1:]:
            if part.startswith("type:"):
                type = part.split(":", 1)[1]
            elif part.startswith("default:"):
                default = part.split(":", 1)[1]

        return Placeholder(name=name, type=type, default=default)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Placeholder):
            return False
        return (
            self.name == other.name
            and self.type == other.type
            and self.default == other.default
        )

    def __hash__(self) -> int:
        return hash((self.name, self.type, self.default))
