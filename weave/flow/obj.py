from typing import Optional, Any
from pydantic import (
    ConfigDict,
    model_validator,
    ValidatorFunctionWrapHandler,
    ValidationInfo,
    BaseModel,
)

# import pydantic

from weave import box
from weave.trace.op import Op
from weave.weave_client import get_ref
from weave.trace.vals import ObjectRecord, TraceObject


class Object(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    # Allow Op attributes
    model_config = ConfigDict(
        ignored_types=(Op,),
        arbitrary_types_allowed=True,
        protected_namespaces=(),
        extra="forbid",
    )

    __str__ = BaseModel.__repr__

    # This is a "wrap" validator meaning we can run our own logic before
    # and after the standard pydantic validation.
    @model_validator(mode="wrap")
    @classmethod
    def handle_relocatable_object(
        cls, v: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
    ) -> Any:
        if isinstance(v, TraceObject):
            # This is a relocated object, so destructure it into a dictionary
            # so pydantic can validate it.
            keys = v._val.__dict__.keys()
            fields = {}
            for k in keys:
                if k.startswith("_"):
                    continue
                val = getattr(v, k)
                if isinstance(val, box.BoxedNone):
                    val = None
                fields[k] = val
            # pydantic validation will construct a new pydantic object
            def is_ignored_type(v: type) -> bool:
                return isinstance(v, cls.model_config["ignored_types"])

            allowed_fields = {k: v for k, v in fields.items() if not is_ignored_type(v)}
            new_obj = handler(allowed_fields)
            for k, v in fields.items():
                if is_ignored_type(v):
                    new_obj.__dict__[k] = v

            # transfer ref to new object
            # We can't attach a ref directly to pydantic objects yet.
            # TODO: fix this. I think dedupe may make it so the user data ends up
            #    working fine, but not setting a ref here will cause the client
            #    to do extra work.
            # if isinstance(v, TraceObject):
            #     ref = get_ref(v)
            #     new_obj
            # return new_obj

            return new_obj
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
