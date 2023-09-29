import typing
import pyarrow as pa
import numpy as np

from .arrow import arrow_as_array, offsets_starting_at_zero

from ..api import op, OpVarArgs
from ..decorator_arrow_op import arrow_op
from .. import weave_types as types
from ..ops_primitives import _dict_utils
from ..ops_primitives import projection_utils
from ..language_features.tagging import (
    process_opdef_output_type,
)
from .arrow_tags import direct_add_arrow_tags
from . import convert

from .constructors import (
    vectorized_container_constructor_preprocessor,
    vectorized_input_types,
)
from .list_ import ArrowWeaveList, ArrowWeaveListType


def typeddict_pick_output_type(input_types):
    output_type = _dict_utils.typeddict_pick_output_type(input_types)
    return process_opdef_output_type.op_make_type_tagged_resolver(
        output_type,
        process_opdef_output_type.op_get_tag_type_resolver(input_types["self"]),
    )


def _struct_array_field_names(array: pa.StructArray) -> list[str]:
    return [array.type.field(i).name for i in range(array.type.num_fields)]


def _arrow_val_tag_wrapper(
    array: pa.Array,
) -> typing.Tuple[typing.Callable[[pa.Array], pa.Array], pa.Array]:
    tags = None
    if isinstance(array, pa.StructArray):
        fields = _struct_array_field_names(array)
        if len(fields) == 2 and set(fields) == set(["_tag", "_value"]):
            tags = array.field("_tag")
            array = array.field("_value")

    def wrapper(res: pa.Array) -> typing.Any:
        if tags is not None:
            return direct_add_arrow_tags(res, tags)
        else:
            return res

    return wrapper, array


def _awl_pick(array: pa.Array, path: list[str]) -> pa.Array:
    def default_return():
        return pa.array([None] * len(array))

    if len(path) == 0:
        return default_return()
    tag_wrapper, inner_array = _arrow_val_tag_wrapper(array)
    key = path[0]
    next_path = path[1:]
    if isinstance(inner_array, pa.ListArray) and key == "*":
        if len(next_path) == 0:
            return array
        else:
            flattened_results = _awl_pick(inner_array.flatten(), next_path)
            rolled_results = pa.ListArray.from_arrays(
                offsets_starting_at_zero(inner_array), flattened_results
            )
            return tag_wrapper(rolled_results)
    elif isinstance(inner_array, pa.StructArray):
        all_names = _struct_array_field_names(inner_array)
        if key == "*":
            all_columns = [
                _awl_pick(inner_array.field(name), next_path) for name in all_names
            ]
            return tag_wrapper(pa.StructArray.from_arrays(all_columns, all_names))
        else:
            if key not in all_names:
                return default_return()
            key_val = inner_array.field(key)
            if len(next_path) == 0:
                res = key_val
            else:
                res = _awl_pick(key_val, next_path)
            return tag_wrapper(res)
    else:
        return default_return()


@arrow_op(
    name="ArrowWeaveListTypedDict-pick",
    input_type={"self": ArrowWeaveListType(types.TypedDict({})), "key": types.String()},
    output_type=lambda input_types: ArrowWeaveListType(
        typeddict_pick_output_type(
            {"self": input_types["self"].object_type, "key": input_types["key"]}
        )
    ),
    all_args_nullable=False,
)
def pick(self, key):
    object_type = typeddict_pick_output_type(
        {"self": self.object_type, "key": types.Const(types.String(), key)}
    )
    data = arrow_as_array(self._arrow_data)
    path = _dict_utils.split_escaped_string(key)
    result = _awl_pick(data, path)
    return ArrowWeaveList(result, object_type, self._artifact)


def _ensure_awl_for_merge(
    ensure_target: typing.Union[dict, ArrowWeaveList],
    compare_target: typing.Union[dict, ArrowWeaveList],
) -> ArrowWeaveList:
    if not isinstance(ensure_target, ArrowWeaveList):
        assert isinstance(compare_target, ArrowWeaveList)
        utility_awl = convert.to_arrow([ensure_target])
        return ArrowWeaveList(
            pa.repeat(ensure_target, len(compare_target)),
            utility_awl.object_type,
            utility_awl._artifact,
        )
    return ensure_target


MaybeTypedDictType = types.optional(types.TypedDict({}))
AWLMaybeTypedDictType = ArrowWeaveListType(MaybeTypedDictType)


@op(
    name="ArrowWeaveList-_preprocessMerge",
    input_type={
        "self": types.union(AWLMaybeTypedDictType, MaybeTypedDictType),
        "other": (
            lambda input_types: AWLMaybeTypedDictType
            if MaybeTypedDictType.assign_type(input_types["self"])
            else types.union(AWLMaybeTypedDictType, MaybeTypedDictType)
        ),
    },
    output_type=(
        lambda input_types: input_types["self"]
        if ArrowWeaveListType().assign_type(input_types["self"])
        else ArrowWeaveListType(input_types["self"])
    ),
    hidden=True,
)
def preprocess_merge(self, other):
    "Preprocesses the merge operation to ensure that both inputs are ArrowWeaveLists."
    return _ensure_awl_for_merge(self, other)


@arrow_op(
    name="ArrowWeaveListTypedDict-merge",
    input_type={
        # Optional inner type to support nullability
        "self": ArrowWeaveListType(types.optional(types.TypedDict({}))),
        "other": ArrowWeaveListType(types.TypedDict({})),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        _dict_utils.typeddict_merge_output_type(
            {
                "self": input_types["self"].object_type,
                "other": input_types["other"].object_type,
            }
        )
    ),
    all_args_nullable=False,
)
def merge(self, other):
    field_arrays: dict[str, pa.Array] = {}
    for arrow_weave_list in (self, other):
        if isinstance(arrow_weave_list.object_type, types.NoneType):
            continue
        for key in arrow_weave_list.object_type.property_types:
            if isinstance(arrow_weave_list._arrow_data, pa.Table):
                field_arrays[key] = arrow_weave_list._arrow_data[key].combine_chunks()
            else:
                field_arrays[key] = arrow_weave_list._arrow_data.field(key)

    if isinstance(self._arrow_data, pa.Array):
        mask = pa.compute.is_null(self._arrow_data)
    else:
        # TODO: implement for table, chunkedarray etc
        mask = None

    field_names, arrays = tuple(zip(*field_arrays.items()))
    new_array = pa.StructArray.from_arrays(arrays=arrays, names=field_names, mask=mask)  # type: ignore

    result = ArrowWeaveList(
        new_array,
        _dict_utils.typeddict_merge_output_type(
            {"self": self.object_type, "other": other.object_type}
        ),
        self._artifact,
    )

    return result


# this function handles the following case:
# types.TypeRegistry.type_of(awl1) == tagged_value_type.TaggedValueType(
#    types.TypedDict({"outer1": types.String()}), ArrowWeaveListType(types.Int())
# )
# types.TypeRegistry.type_of(awl2) == tagged_value_type.TaggedValueType(
#    types.TypedDict({"outer2": types.String()}), ArrowWeaveListType(types.Int())
# )
#
# push down tags on list to tags on dict elements
# types.TypeRegistry.type_of(arrow_dict_(a=awl1, b=awl2)) == ArrowWeaveListType(
#    types.TypedDict(
#        {
#            "a": tagged_value_type.TaggedValueType(
#                types.TypedDict({"outer1": types.String()}), types.Int()
#            ),
#            "b": tagged_value_type.TaggedValueType(
#                types.TypedDict({"outer2": types.String()}), types.Int()
#            ),
#        }
#    )
# )


def vectorized_dict_output_type(input_types):
    prop_types = vectorized_input_types(input_types)
    return ArrowWeaveListType(types.TypedDict(prop_types))


@op(
    name="ArrowWeaveList-vectorizedDict",
    input_type=OpVarArgs(types.Any()),
    output_type=vectorized_dict_output_type,
    render_info={"type": "function"},
)
def arrow_dict_(**d):
    res = vectorized_container_constructor_preprocessor(d)
    table = pa.Table.from_arrays(res.arrays, list(d.keys()))
    return ArrowWeaveList(table, types.TypedDict(res.prop_types), res.artifact)


@arrow_op(
    name="ArrowWeaveList-2DProjection",
    input_type={
        "table": ArrowWeaveListType(types.TypedDict({})),
        "projectionAlgorithm": types.String(),
        "inputCardinality": types.String(),
        "inputColumnNames": types.List(types.String()),
        "algorithmOptions": types.TypedDict({}),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        types.TypedDict(
            {
                "projection": types.TypedDict(
                    {"x": types.Number(), "y": types.Number()}
                ),
                "source": input_types["table"].object_type,
            }
        )
    ),
)
def awl_2d_projection(
    table,
    projectionAlgorithm,
    inputCardinality,
    inputColumnNames,
    algorithmOptions,
):
    inputColumnNames = list(set(inputColumnNames))
    source_column = arrow_as_array(table._arrow_data)
    data = table._arrow_data_asarray_no_tags()

    def default_projection():
        return np.zeros((len(data), 2))

    if len(inputColumnNames) == 0 or len(data) < 2:
        np_projection = default_projection()
    else:
        if inputCardinality == "single":
            path = _dict_utils.split_escaped_string(inputColumnNames[0])
            np_array_of_embeddings = np.stack(
                _awl_pick(data, path).to_numpy(False), axis=0
            )
        else:
            column_data = [
                _awl_pick(data, _dict_utils.split_escaped_string(c))
                for c in inputColumnNames
            ]
            # Filter out null columns
            column_data = [
                col for col in column_data if not isinstance(col, pa.NullArray)
            ]
            np_array_of_embeddings = np.array(column_data).T

        # coerce to float to turn Nones into nans
        np_array_of_embeddings = np_array_of_embeddings.astype("f")

        # impute nans with average value for column - this handles the case
        # where we have a column of Optional[number]
        none_indices = np.argwhere(np.isnan(np_array_of_embeddings))
        column_indices = none_indices[:, 1]

        np.put(
            np_array_of_embeddings,
            none_indices,
            np.nanmean(np_array_of_embeddings, axis=0)[column_indices],
        )

        # if any remaining nans (can only happen if all values in a column are nan), replace with zeros
        # such columns will be removed in the next step
        np_array_of_embeddings = np.nan_to_num(np_array_of_embeddings)

        # remove 0-only columns
        np_array_of_embeddings = np_array_of_embeddings[
            :, ~((np_array_of_embeddings == 0).all(axis=0))
        ]
        # If the selected data is not a 2D array, or if it has less than 2 columns, then
        # we can't perform a 2D projection. In this case, we just return a 2D array of
        # zeros.
        if (
            len(np_array_of_embeddings.shape) != 2
            or np_array_of_embeddings.shape[1] < 2
        ):
            np_projection = default_projection()
        else:
            np_array_of_embeddings = np.nan_to_num(np_array_of_embeddings, copy=False)
            np_projection = projection_utils.perform_2D_projection_with_timeout(
                np_array_of_embeddings, projectionAlgorithm, algorithmOptions
            )
    x_column = np_projection[:, 0]
    y_column = np_projection[:, 1]

    projection_column = pa.StructArray.from_arrays(
        [pa.array(x_column), pa.array(y_column)], ["x", "y"]
    )

    projection_column = pa.StructArray.from_arrays(
        [projection_column, source_column], ["projection", "source"]
    )

    return ArrowWeaveList(
        projection_column,
        types.TypedDict(
            {
                "projection": types.TypedDict(
                    {
                        "x": types.Number(),
                        "y": types.Number(),
                    }
                ),
                "source": table.object_type,
            }
        ),
        table._artifact,
    )


@arrow_op(
    name="ArrowWeaveList-projection2D",
    input_type={
        "table": ArrowWeaveListType(types.TypedDict({})),
        "projectionAlgorithm": types.String(),
        "inputCardinality": types.String(),
        "inputColumnNames": types.List(types.String()),
        "algorithmOptions": types.TypedDict({}),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        types.TypedDict(
            {
                "projection": types.TypedDict(
                    {"x": types.Number(), "y": types.Number()}
                ),
                "source": input_types["table"].object_type,
            }
        )
    ),
)
def awl_projection_2d(
    table,
    projectionAlgorithm,
    inputCardinality,
    inputColumnNames,
    algorithmOptions,
):
    inputColumnNames = list(set(inputColumnNames))
    source_column = arrow_as_array(table._arrow_data)
    data = table._arrow_data_asarray_no_tags()

    def default_projection():
        return np.array([[0, 0] for row in data])

    if len(inputColumnNames) == 0 or len(data) < 2:
        np_projection = default_projection()
    else:
        if inputCardinality == "single":
            path = _dict_utils.split_escaped_string(inputColumnNames[0])
            np_array_of_embeddings = np.stack(
                _awl_pick(data, path).to_numpy(False), axis=0
            )
        else:
            column_data = [
                _awl_pick(data, _dict_utils.split_escaped_string(c))
                for c in inputColumnNames
            ]
            # Filter out null columns
            column_data = [
                col for col in column_data if not isinstance(col, pa.NullArray)
            ]
            np_array_of_embeddings = np.array(column_data).T
        # remove 0-only columns
        np_array_of_embeddings = np_array_of_embeddings[
            :, ~(np_array_of_embeddings.sum(axis=0) == 0)
        ]
        # If the selected data is not a 2D array, or if it has less than 2 columns, then
        # we can't perform a 2D projection. In this case, we just return a 2D array of
        # zeros.
        if (
            len(np_array_of_embeddings.shape) != 2
            or np_array_of_embeddings.shape[1] < 2
        ):
            np_projection = default_projection()
        else:
            np_array_of_embeddings = np.nan_to_num(np_array_of_embeddings, copy=False)
            np_projection = projection_utils.perform_2D_projection_with_timeout(
                np_array_of_embeddings, projectionAlgorithm, algorithmOptions
            )
    x_column = np_projection[:, 0]
    y_column = np_projection[:, 1]

    projection_column = pa.StructArray.from_arrays(
        [pa.array(x_column), pa.array(y_column)], ["x", "y"]
    )

    projection_column = pa.StructArray.from_arrays(
        [projection_column, source_column], ["projection", "source"]
    )

    return ArrowWeaveList(
        projection_column,
        types.TypedDict(
            {
                "projection": types.TypedDict(
                    {
                        "x": types.Number(),
                        "y": types.Number(),
                    }
                ),
                "source": table.object_type,
            }
        ),
        table._artifact,
    )


@op(
    name="ArrowWeaveListTypedDict-keys",
    input_type={"self": ArrowWeaveListType(types.TypedDict({}))},
    output_type=lambda input_types: ArrowWeaveListType(types.List(types.String())),
)
def keys(self):
    keys = list(self.object_type.property_types.keys())
    return convert.to_arrow(
        [keys] * len(self), types.List(types.List(types.String())), self._artifact
    )


@op(
    name="ArrowWeaveListTypedDict-columnNames",
    hidden=True,
    input_type={"self": ArrowWeaveListType(types.TypedDict({}))},
    output_type=lambda input_types: ArrowWeaveListType(types.String()),
)
def columnNames(self):
    return convert.to_arrow(
        list(self.object_type.property_types.keys()),
        types.List(types.String()),
        self._artifact,
    )


def _with_column_type(cur_type: types.Type, key: str, new_col_type: types.Type):
    if not isinstance(cur_type, types.TypedDict):
        cur_type = types.TypedDict()
    path = _dict_utils.split_escaped_string(key)

    property_types = {**cur_type.property_types}

    if len(path) > 1:
        return _with_column_type(
            cur_type,
            path[0],
            _with_column_type(
                property_types[path[0]], ".".join(path[1:]), new_col_type
            ),
        )

    col_names = list(property_types.keys())
    try:
        key_index = col_names.index(key)
    except ValueError:
        key_index = None
    if key_index is not None:
        property_types.pop(key)
        col_names.pop(key_index)
    property_types[key] = new_col_type
    return types.TypedDict(property_types)


def _with_columns_output_type(input_type):
    new_col_types = input_type["cols"]
    obj_type = input_type["self"].object_type
    for k, v in new_col_types.property_types.items():
        # added column type is optional, because we may need to extend with None
        # if it is too short.
        obj_type = _with_column_type(obj_type, k, v.object_type)
    return ArrowWeaveListType(obj_type)


@op(
    name="ArrowWeaveListTypedDict-with_columns",
    hidden=True,
    input_type={
        "self": ArrowWeaveListType(types.TypedDict({})),
        "cols": types.Dict(types.String(), ArrowWeaveListType()),
    },
    output_type=_with_columns_output_type,
)
def with_columns(self, cols):
    for col_val in cols.values():
        if len(self) != len(col_val):
            return None
    return self.with_columns(cols)
