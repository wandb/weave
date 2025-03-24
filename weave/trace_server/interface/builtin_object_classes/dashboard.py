from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class Data(BaseModel):
    query: str


class Dashboard(base_object_def.BaseObject):
    # Avoiding confusion around object_id + name
    label: str

    data: list[Data] = []
