from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class ModelMode(str, Enum):
    COMPLETION = "completion"
    CHAT = "chat"


class ModelParams(BaseModel):
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stop: Optional[Union[str, list[str]]] = None


class ProviderModel(base_object_def.BaseObject):
    name: str
    provider: base_object_def.RefStr
    max_tokens: int
    mode: ModelMode = ModelMode.CHAT


class LLMModel(base_object_def.BaseObject):
    name: str
    provider_model: base_object_def.RefStr
    prompt: Optional[base_object_def.RefStr] = None
    default_params: ModelParams = ModelParams()
