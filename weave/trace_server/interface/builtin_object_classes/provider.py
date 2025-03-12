from enum import Enum

from weave.trace_server.interface.builtin_object_classes import base_object_def


class ReturnType(str, Enum):
    OPENAI = "openai"


class Provider(base_object_def.BaseObject):
    base_url: str
    api_key_name: str
    extra_headers: dict[str, str] = {}
    return_type: ReturnType = ReturnType.OPENAI
