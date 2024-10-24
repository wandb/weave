from typing import Literal

from pydantic import BaseModel

from weave.trace_server.interface.collections.collection import Collection


class _BuiltinAction(BaseModel):
    action_type: Literal["builtin"] = "builtin"
    name: str
    digest: str = "*"

class ActionWithConfig(BaseModel):
    name: str
    action: _BuiltinAction
    config: dict

class ActionOpMapping(BaseModel):
    name: str  # uggg, want to get rid of this
    action: ActionWithConfig
    op_name: str
    op_digest: str
    input_mapping: dict[str, str]  # Input field name -> Call selector

action_with_config_collection = Collection(
    name="ActionWithConfig",
    base_model_spec=ActionWithConfig,
)

action_op_mapping_collection = Collection(
    name="ActionOpMapping",
    base_model_spec=ActionOpMapping,
)
