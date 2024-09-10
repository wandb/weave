from typing import Any, Literal

Templating = Literal["weave", "none"]

Params = dict[str, Any]


ROLE_COLORS = {
    "system": "bold blue",
    "user": "bold green",
    "assistant": "bold magenta",
}


def color_role(role: str) -> str:
    color = ROLE_COLORS.get(role)
    if color is None:
        return role
    return f"[{color}]{role}[/]"
