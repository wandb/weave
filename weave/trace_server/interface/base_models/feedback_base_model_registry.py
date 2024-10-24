from openai import BaseModel


class ActionScore(BaseModel):
    configured_action_ref: str
    output: dict


feedback_base_models: list[BaseModel] = [ActionScore]
