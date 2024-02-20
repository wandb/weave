import typing
from typing import Optional, Type, Tuple, Dict, Any
from pydantic import (
    ConfigDict,
    model_validator,
    ValidatorFunctionWrapHandler,
    ValidationInfo,
)
from pydantic._internal._model_construction import ModelMetaclass
import pydantic
import inspect

from weave.op_def import OpDef, BoundOpDef
from .. import ref_util
from .. import box
from .. import ref_base


class ObjectMeta(ModelMetaclass):
    def __new__(
        cls: Type["ObjectMeta"], name: str, bases: Tuple[type, ...], dct: Dict[str, Any]
    ) -> "ObjectMeta":
        # Modify an OpDef names to include the class name.
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
    name: Optional[str] = None
    description: Optional[str] = None

    # Allow OpDef attributes
    model_config = ConfigDict(ignored_types=(OpDef,), arbitrary_types_allowed=True)

    def __getattribute__(self, name: str) -> Any:
        attribute = super().__getattribute__(name)
        if name not in super().__getattribute__("model_fields"):
            return attribute
        return ref_util.val_with_relative_ref(
            self, attribute, [ref_util.OBJECT_ATTRIBUTE_EDGE_TYPE, str(name)]
        )

    # This is a "wrap" validator meaning we can run our own logic before
    # and after the standard pydantic validation.
    @model_validator(mode="wrap")
    @classmethod
    def handle_relocatable_object(
        cls, v: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
    ) -> Any:
        if hasattr(v, "_weave_obj_fields"):
            # This is a relocated weave object, so destructure it into a dictionary
            # so pydantic can validate it.
            fields = {}
            for k in v._weave_obj_fields:
                val = getattr(v, k)
                if isinstance(val, box.BoxedNone):
                    val = None
                fields[k] = val
            # pydantic validation will construct a new pydantic object
            new_obj = handler(fields)
            # transfer ref to new object
            ref = ref_base.get_ref(v)
            if ref is not None:
                ref_base._put_ref(new_obj, ref)
            return new_obj
        # otherwise perform standard pydantic validation
        return handler(v)
