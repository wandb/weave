from enum import Enum
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def
from weave.trace_server.interface.builtin_object_classes.provider import ReturnType
from weave.trace_server.interface.builtin_object_classes.prompt import Prompt


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


class CostConfig(BaseModel):
    prompt_token_cost_per_1m: float = 0.0
    prompt_token_cost_unit: str = "USD"
    completion_token_cost_per_1m: float = 0.0
    completion_token_cost_unit: str = "USD"


class LLMModel(base_object_def.BaseObject):
    name: str
    max_tokens: int
    provider: base_object_def.RefStr
    extra_headers: Dict[str, str] = {}
    cost: CostConfig = CostConfig()
    return_type: Optional[ReturnType] = None  # If None, uses provider default
    mode: ModelMode = ModelMode.CHAT

    default_params: ModelParams = ModelParams()
    prompt: Optional[base_object_def.RefStr] = None  # Reference to a Prompt object


class PlaygroundProvider(base_object_def.BaseObject):
    provider: base_object_def.RefStr
    models: list[base_object_def.RefStr]
    hidden_models: list[base_object_def.RefStr] = []
