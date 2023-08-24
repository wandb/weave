import typing
import pyarrow as pa
from pyarrow import compute as pc

from .. import weave_types as types
from ..decorator_arrow_op import arrow_op
from ..language_features.tagging import tagged_value_type

from .arrow import ArrowWeaveListType, arrow_as_array
from .list_ import ArrowWeaveList


def _arrowweavelistlist_listindex_output_type(input_types):
    self = input_types["self"]
    new_type = types.optional(self.object_type.object_type)
    if new_type == types.UnknownType():
        # if our object type was Unknown, it means it was an empty list.
        # indexing into that will always produce None
        new_type = types.NoneType()
    return new_type


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
        _arrowweavelistlist_listindex_output_type(input_types)
    ),
)
def listindex(self, index):
    a = arrow_as_array(self._arrow_data)
    if index == None:
        return ArrowWeaveList(
            pa.nulls(len(a)),
            types.NoneType(),
            self._artifact,
        )
    if not isinstance(index, int):
        index = arrow_as_array(index._arrow_data)
        # Not handling negative indexes at the moment
        assert pa.compute.all(pa.compute.greater_equal(index, 0))

    start_indexes = a.offsets[:-1]
    end_indexes = a.offsets[1:]
    if isinstance(index, int) and index < 0:
        take_indexes = pa.compute.add(end_indexes, index)
        oob = pa.compute.less(take_indexes, start_indexes)
    else:
        take_indexes = pa.compute.add(start_indexes, index)
        oob = pa.compute.greater_equal(take_indexes, end_indexes)
    take_indexes = pa.compute.if_else(oob, None, take_indexes)
    result = a.flatten().take(take_indexes)
    return ArrowWeaveList(
        result,
        _arrowweavelistlist_listindex_output_type({"self": self}),
        self._artifact,
    )


def _list_op_output_object_type(input_types):
    self_type = input_types["self"]
    from .. import op_def

    def _remove_tags(t):
        if isinstance(t, tagged_value_type.TaggedValueType):
            return t.value
        return t

    self_type_without_tags = op_def.map_type(self_type, _remove_tags)
    return self_type_without_tags.object_type.object_type


def list_dim_downresolver(
    self: ArrowWeaveList, arrow_operation_name: str, output_object_type=None
):
    without_tags = self.without_tags()
    a = arrow_as_array(without_tags._arrow_data)
    values = a.flatten()

    start_indexes = a.offsets[:-1]
    end_indexes = a.offsets[1:]
    non_0len = pa.compute.not_equal(start_indexes, end_indexes)
    t = pa.Table.from_arrays([a.value_parent_indices(), values], ["keys", "values"])
    g = t.group_by("keys")
    non_0len_agged = g.aggregate([("values", arrow_operation_name)])[
        f"values_{arrow_operation_name}"
    ]
    nulls = pa.nulls(len(a), type=non_0len_agged.type)
    result = pa.compute.replace_with_mask(
        nulls, non_0len, non_0len_agged.combine_chunks()
    )
    if output_object_type == None:
        output_object_type = without_tags.object_type.object_type  # type: ignore
    return ArrowWeaveList(
        result,
        output_object_type,
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListListNumber-listnumbercount",
    input_type={
        "self": ArrowWeaveListType(
            types.optional(
                types.UnionType(
                    types.List(),
                    ArrowWeaveListType(),
                )
            )
        ),
    },
    output_type=ArrowWeaveListType(types.Int()),
)
def list_numbers_count(self):
    return list_dim_downresolver(self, "count", types.Int())


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
        _list_op_output_object_type(input_types)
    ),
)
def list_numbers_max(self):
    return list_dim_downresolver(self, "max")


@arrow_op(
    name="ArrowWeaveListListNumber-listnumbermin",
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
        _list_op_output_object_type(input_types)
    ),
)
def list_numbers_min(self):
    return list_dim_downresolver(self, "min")


@arrow_op(
    name="ArrowWeaveListListNumber-listnumbersum",
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
        _list_op_output_object_type(input_types)
    ),
)
def list_numbers_sum(self):
    return list_dim_downresolver(self, "sum")


@arrow_op(
    name="ArrowWeaveListListNumber-listnumberavg",
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
        _list_op_output_object_type(input_types)
    ),
)
def list_numbers_avg(self):
    return list_dim_downresolver(self, "mean")


# This iterates over the outer list in python but keeps the inner comparisons vectorized
# in arrow.
def compare_sublists(array1: pa.ListArray, array2: pa.ListArray) -> pa.Array:
    if len(array1) != len(array2):
        raise ValueError("The input arrays have different lengths")

    result = []
    flattened1 = array1.flatten()
    flattened2 = array2.flatten()
    offsets1 = array1.offsets.to_pylist()
    offsets2 = array2.offsets.to_pylist()

    for i in range(len(array1)):
        start1, end1 = offsets1[i], offsets1[i + 1]
        start2, end2 = offsets2[i], offsets2[i + 1]
        sublist1 = flattened1.slice(start1, end1 - start1)
        sublist2 = flattened2.slice(start2, end2 - start2)
        result.append(sublist1.equals(sublist2))

    return result


@arrow_op(
    name="ArrowWeaveListListNumber-equal",
    input_type={
        "self": ArrowWeaveListType(
            types.optional(
                types.UnionType(
                    types.List(types.optional(types.Number())),
                    ArrowWeaveListType(types.optional(types.Number())),
                )
            )
        ),
        "other": ArrowWeaveListType(
            types.optional(
                types.UnionType(
                    types.List(types.optional(types.Number())),
                    ArrowWeaveListType(types.optional(types.Number())),
                )
            )
        ),
    },
    output_type=lambda input_types: ArrowWeaveListType(types.Boolean()),
)
def list_equal(self, other):
    return ArrowWeaveList(
        pa.array(
            compare_sublists(
                self.without_tags()._arrow_data, other.without_tags()._arrow_data
            )
        ),
        types.Boolean(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListListNumber-notEqual",
    input_type={
        "self": ArrowWeaveListType(
            types.optional(
                types.UnionType(
                    types.List(types.optional(types.Number())),
                    ArrowWeaveListType(types.optional(types.Number())),
                )
            )
        ),
        "other": ArrowWeaveListType(
            types.optional(
                types.UnionType(
                    types.List(types.optional(types.Number())),
                    ArrowWeaveListType(types.optional(types.Number())),
                )
            )
        ),
    },
    output_type=lambda input_types: ArrowWeaveListType(types.Boolean()),
)
def list_not_equal(self, other):
    return ArrowWeaveList(
        pc.invert(list_equal.resolve_fn(self, other)._arrow_data),
        types.Boolean(),
        self._artifact,
    )


def _vectorized_dropna_object_type(
    outer_object_type: typing.Union[types.List, ArrowWeaveListType, types.UnionType]
) -> types.Type:
    outer_is_optional = types.is_optional(outer_object_type)
    if outer_is_optional:
        container_type = types.non_none(outer_object_type)
    else:
        container_type = outer_object_type
    container_class = typing.cast(
        typing.Union[typing.Type[ArrowWeaveListType], typing.Type[types.List]],
        container_type.__class__,
    )
    element_type = typing.cast(
        typing.Union[types.List, ArrowWeaveListType], container_type
    ).object_type

    ret_type = container_class(types.non_none(element_type))
    if outer_is_optional:
        ret_type = types.optional(ret_type)  # type: ignore
    return ret_type


@arrow_op(
    name="ArrowWeaveListList-vectorizedDropna",
    input_type={
        "self": ArrowWeaveListType(types.List()),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        _vectorized_dropna_object_type(input_types["self"].object_type)
    ),
)
def dropna(self):
    a = arrow_as_array(self._arrow_data)

    # NOTE: does not work for unions right now because of pyarrow bugs for null union values
    # e.g., pyarrow.compute.is_null(UnionScalar<None>) segfaults
    # pyarrow.compute.is_null(UnionArray<1, 2, None, None, "a">) returns [True, True, True, True, True]
    start_indexes = a.offsets[:-1]
    end_indexes = a.offsets[1:]
    flattened = a.flatten()
    non_null = pa.compute.cast(
        pa.compute.invert(pa.compute.is_null(flattened)), a.offsets.type
    )
    new_data = pa.compute.drop_null(flattened)
    cumulative_non_null_counts = pa.compute.cumulative_sum(non_null)
    new_offsets = cumulative_non_null_counts.take(pa.compute.subtract(end_indexes, 1))
    new_offsets = pa.concat_arrays([start_indexes[:1], new_offsets])
    unflattened = pa.ListArray.from_arrays(
        new_offsets, new_data, mask=pa.compute.is_null(a)
    )

    return ArrowWeaveList(
        unflattened,
        _vectorized_dropna_object_type(self.object_type),
        self._artifact,
    )
