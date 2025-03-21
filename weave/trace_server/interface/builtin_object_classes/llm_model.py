from typing import Optional, Union

from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class LLMModelDefaultParams(BaseModel):
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stop: Optional[Union[str, list[str]]] = None


class LLMModel(base_object_def.BaseObject):
    provider_model: base_object_def.RefStr
    prompt: Optional[base_object_def.RefStr] = None
    default_params: LLMModelDefaultParams = Field(default_factory=LLMModelDefaultParams)
