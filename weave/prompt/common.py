# TODO: Maybe use an enum or something to lock down types more

ROLE_COLORS: dict[str, str] = {
    "system": "bold blue",
    "user": "bold green",
    "assistant": "bold magenta",
}


def color_role(role: str) -> str:
    color = ROLE_COLORS.get(role)
    if color:
        return f"[{color}]{role}[/]"
    return role
