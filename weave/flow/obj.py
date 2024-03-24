from typing import Optional
from pydantic import ConfigDict
import pydantic

from weave.trace.op import Op


class Object(pydantic.BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    # Allow Op attributes
    model_config = ConfigDict(
        ignored_types=(Op,),
        arbitrary_types_allowed=True,
        protected_namespaces=(),
        extra="forbid",
    )

    __str__ = pydantic.BaseModel.__repr__


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
