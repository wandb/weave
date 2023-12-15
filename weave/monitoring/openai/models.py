from typing import List, Optional

from .. import monitor
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from pydantic import BaseModel, Field
from ... import weave_types as types


class ModelTokensConfig(BaseModel):
    per_message: int = 0
    per_name: int = 0


class CombinedChoice(BaseModel):
    content: str = ""
    finish_reason: Optional[str] = None
    role: Optional[str] = None
    function_call: Optional[str] = None
    tool_calls: Optional[str] = None


class ChatCompletionRequestMessage(ChatCompletionMessage):
    role: str = ""


class ChatCompletionRequest(BaseModel):
    class Config:
        use_enum_values = True

    model: str = ""
    messages: List[ChatCompletionRequestMessage] = Field(default_factory=list)
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = None


class Context(BaseModel):
    class Config:
        extra = "allow"

    # span: Optional[monitor.Span]
    inputs: Optional[ChatCompletionRequest] = None
    outputs: Optional[ChatCompletion] = None
