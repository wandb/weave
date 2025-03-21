from enum import Enum

from pydantic import Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class ProviderReturnType(str, Enum):
    OPENAI = "openai"


class Provider(base_object_def.BaseObject):
    base_url: str
    api_key_name: str
    extra_headers: dict[str, str] = Field(default_factory=dict)
    return_type: ProviderReturnType = Field(default=ProviderReturnType.OPENAI)


class ProviderModel(base_object_def.BaseObject):
    provider: base_object_def.RefStr
    max_tokens: int
