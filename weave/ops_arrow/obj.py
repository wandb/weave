import typing
import pyarrow as pa

from ..api import type_of
from ..decorator_arrow_op import arrow_op
from .. import weave_types as types
from ..ops_primitives import obj as primitives_obj

from .list_ import ArrowWeaveList, ArrowWeaveListType


@arrow_op(
    name="ArrowWeaveListObject-__vectorizedGetattr__",
    input_type={
        "self": ArrowWeaveListType(types.Any()),
        "name": types.String(),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        primitives_obj.getattr_output_type(
            {"self": input_types["self"].object_type, "name": input_types["name"]}
        )
    ),
    all_args_nullable=False,
)
def arrow_getattr(self, name):
    ref_array = self._arrow_data
    # deserialize objects
    objects: list[typing.Any] = []
    for ref in ref_array:
        if ref.as_py() is None:
            objects.append(None)
        else:
            objects.append(getattr(self._mapper.apply(ref.as_py()), name))

    object_type = type_of(objects[0])
    return ArrowWeaveList(pa.array(objects), object_type, self._artifact)
