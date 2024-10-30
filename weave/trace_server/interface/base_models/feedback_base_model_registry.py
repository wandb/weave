from typing import Any

from pydantic import BaseModel


class ActionScore(BaseModel):
    configured_action_ref: str
    output: Any


feedback_base_models: list[type[BaseModel]] = [ActionScore]
