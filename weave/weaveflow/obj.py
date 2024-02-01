import typing
from typing import Optional
from pydantic import ConfigDict
from pydantic._internal._model_construction import ModelMetaclass
import pydantic
import inspect

from weave.op_def import OpDef, BoundOpDef


class ObjectMeta(ModelMetaclass):
    def __new__(cls, name, bases, dct):
        original_class = super(ObjectMeta, cls).__new__(cls, name, bases, dct)
        for attr, bound_op_def in inspect.getmembers(
            original_class, lambda x: isinstance(x, BoundOpDef)
        ):
            bound_op_def = typing.cast(BoundOpDef, bound_op_def)
            unbound_op_def = bound_op_def.op_def
            if unbound_op_def.name.startswith("op-"):
                unbound_op_def.name = f"{name}-{unbound_op_def.name[3:]}"
        return original_class


class Object(pydantic.BaseModel, metaclass=ObjectMeta):
    name: Optional[str] = "hello"
    description: Optional[str] = None

    # Allow OpDef attributes
    model_config = ConfigDict(ignored_types=(OpDef,))
