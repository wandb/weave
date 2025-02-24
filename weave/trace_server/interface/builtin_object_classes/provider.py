from enum import Enum
from typing import Optional, Dict

from weave.trace_server.interface.builtin_object_classes import base_object_def


class ReturnType(str, Enum):
    OPENAI = "openai"


class Provider(base_object_def.BaseObject):
    name: str
    base_url: str
    api_key_name: str
    description: Optional[str] = None
    extra_headers: Dict[str, str] = {}
    return_type: ReturnType = ReturnType.OPENAI
