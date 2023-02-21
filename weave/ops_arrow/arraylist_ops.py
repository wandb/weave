import pyarrow as pa

from .. import weave_types as types
from ..decorator_arrow_op import arrow_op

from .arrow import ArrowWeaveListType, arrow_as_array
from .list_ import ArrowWeaveList


@arrow_op(
    name="ArrowWeaveListList-listindex",
    input_type={
        "self": ArrowWeaveListType(
            types.optional(types.UnionType(types.List(), ArrowWeaveListType()))
        ),
        "index": types.optional(
            types.UnionType(
                types.Int(),
                types.List(types.optional(types.Int())),
                ArrowWeaveListType(types.optional(types.Int())),
            )
        ),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        types.optional(input_types["self"].object_type.object_type)
    ),
)
def listindex(self, index):
    a = arrow_as_array(self._arrow_data)
    # Not handling negative indexes at the moment
    if index == None:
        return ArrowWeaveList(
            pa.nulls(len(a), type=a.type.value_type),
            types.NoneType(),
            self._artifact,
        )
    if isinstance(index, int):
        assert index >= 0
    else:
        index = arrow_as_array(index._arrow_data)
        assert pa.compute.all(pa.compute.greater_equal(index, 0))

    start_indexes = a.offsets[:-1]
    end_indexes = a.offsets[1:]
    take_indexes = pa.compute.add(start_indexes, index)
    oob = pa.compute.greater_equal(take_indexes, end_indexes)
    take_indexes = pa.compute.if_else(oob, None, take_indexes)
    result = a.flatten().take(take_indexes)
    return ArrowWeaveList(
        result,
        types.optional(self.object_type.object_type),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListListNumber-listnumbermax",
    input_type={
        "self": ArrowWeaveListType(
            types.optional(
                types.UnionType(
                    types.List(types.optional(types.Number())),
                    ArrowWeaveListType(types.optional(types.Number())),
                )
            )
        ),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        input_types["self"].object_type.object_type
    ),
)
def list_numbers_max(self):
    a = arrow_as_array(self._arrow_data)
    start_indexes = a.offsets[:-1]
    end_indexes = a.offsets[1:]
    non_0len = pa.compute.not_equal(start_indexes, end_indexes)
    t = pa.Table.from_arrays(
        [a.value_parent_indices(), a.flatten()], ["keys", "values"]
    )
    g = t.group_by("keys")
    non_0len_maxes = g.aggregate([("values", "max")])["values_max"]
    nulls = pa.nulls(len(a), type=a.type.value_type)
    result = pa.compute.replace_with_mask(
        nulls, non_0len, non_0len_maxes.combine_chunks()
    )
    return ArrowWeaveList(
        result,
        self.object_type.object_type,
        self._artifact,
    )
