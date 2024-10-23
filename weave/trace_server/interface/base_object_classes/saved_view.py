from pydantic import BaseModel
from weave.trace_server.interface.base_object_classes import base_object_def

# class NestedConfig(BaseModel):
#     setting_a: int

class SavedView(base_object_def.BaseObject):
    creator_user_id: str
#    name: str

    # nested: NestedConfig
    # reference: base_object_def.RefStr

# __all__ = ["SavedView"]
