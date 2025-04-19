import weave
from weave.flow.model import Model
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class ResponseFormat(str, Enum):
    JSON = "json"
    TEXT = "text"

    # TODO: Fast follow up
    # JSON_SCHEMA = "jsonschema"


class LLMStructuredCompletionModelDefaultParams(BaseModel):
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stop: Optional[list[str]] = None
    n_times: Optional[int] = None
    response_format: Optional[ResponseFormat] = None
    functions: Optional[list[dict]] = None


# MUST BE NAMED! for distinction in feedback
# Inherit from both Model and BaseObject
class LLMStructuredCompletionModel(Model):
    # <provider>/<model> or ref to a provider model
    llm_model_id: str | base_object_def.RefStr

    # Could use Prompt objects for the message template
    messages_template: list[dict]

    # TODO: Fast follow up with json_schema
    # response_format_schema: dict

    default_params: LLMStructuredCompletionModelDefaultParams = Field(
        default_factory=LLMStructuredCompletionModelDefaultParams
    )

    @weave.op()
    async def predict(self, **inputs) -> dict:
        # TODO: Implement the actual prediction logic
        # This will likely involve calling the underlying model provider
        # based on model_name or custom_provider_model.
        raise NotImplementedError
