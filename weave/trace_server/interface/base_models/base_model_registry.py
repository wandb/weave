from openai import BaseModel

from weave.trace_server.interface.base_models.action_base_models import (
    ActionDispatchFilter,
    ConfiguredAction,
)

base_models: list[BaseModel] = [ConfiguredAction, ActionDispatchFilter]
