from typing import List, Optional

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from pydantic import BaseModel, ConfigDict, Field


class ModelTokensConfig(BaseModel):
    per_message: int
    per_name: int


class CombinedChoice(BaseModel):
    content: str = ""
    finish_reason: Optional[str] = None
    role: Optional[str] = None
    function_call: Optional[str] = None
    tool_calls: Optional[str] = None


class ChatCompletionRequestMessage(ChatCompletionMessage):
    role: str


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True, exclude_none=True)

    model: str
    messages: List[ChatCompletionRequestMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = None


class Context(BaseModel):
    model_config = ConfigDict(extra="allow")

    inputs: ChatCompletionRequest = Field(default_factory=ChatCompletionRequest)
    outputs: ChatCompletion = Field(default_factory=ChatCompletion)
