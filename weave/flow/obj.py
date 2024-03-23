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

from weave.trace.op import Op
from .. import box
from .. import ref_base


class Object(pydantic.BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    # Allow OpDef attributes
    model_config = ConfigDict(
        ignored_types=(Op,),
        arbitrary_types_allowed=True,
        protected_namespaces=(),
        extra="forbid",
    )

    __str__ = pydantic.BaseModel.__repr__

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


# We don't define this directly in the class definition so that VSCode
# doesn't try to navigate to it instead of the target attribute
# def _object_getattribute(self: Object, name: str) -> Any:
#     attribute = object.__getattribute__(self, name)
#     if name not in object.__getattribute__(self, "model_fields"):
#         return attribute
#     return ref_util.val_with_relative_ref(
#         self, attribute, [ref_util.OBJECT_ATTRIBUTE_EDGE_TYPE, str(name)]
#     )


# Object.__getattribute__ = _object_getattribute  # type: ignore
