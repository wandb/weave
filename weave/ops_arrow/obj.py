import pyarrow as pa

from ..api import op, weave_class, type_of
from .. import weave_types as types
from ..ops_primitives import obj as primitives_obj

from .list_ import ArrowWeaveList, ArrowWeaveListType


class ArrowWeaveListObjectType(ArrowWeaveListType):
    name = "ArrowWeaveListObject"
    object_type: types.Type = types.Any()


@weave_class(weave_type=ArrowWeaveListObjectType)
class ArrowWeaveListObject(ArrowWeaveList):
    object_type = types.Any()

    @op(
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
    )
    def __getattr__(self, name):
        ref_array = self._arrow_data
        # deserialize objects
        objects = [getattr(self._mapper.apply(i.as_py()), name) for i in ref_array]
        object_type = type_of(objects[0])
        return ArrowWeaveList(pa.array(objects), object_type)
