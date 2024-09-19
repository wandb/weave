# from types import FrameType

# def get_fully_qualified_method_name(frame: FrameType) -> str:
#     module: str = frame.f_globals.get('__name__', '')
#     try:
#         class_name: str = frame.f_locals['self'].__class__.__name__
#     except KeyError:
#         class_name: str = ''
#     function_name: str = frame.f_code.co_name

#     if class_name:
#         return f"{module}.{class_name}.{function_name}"
#     return f"{module}.{function_name}"


# def is_openai_create_call_frame(frame: FrameType) -> bool:
#     return get_fully_qualified_method_name(frame) == "openai.resources.chat.completions.Completions.create"


# def is_openai_create_call_stack(stack: list[FrameType]) -> bool:
#     return any(is_openai_create_call_frame(frame) for frame in stack)

from enum import Enum


class Role(Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"


ROLE_COLORS: dict[Role, str] = {
    "system": "bold blue",
    "user": "bold green",
    "assistant": "bold magenta",
}


def color_role(role: str) -> str:
    color = ROLE_COLORS.get(role)
    if color is None:
        return role
    return f"[{color}]{role}[/]"
