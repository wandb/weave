import typing
import pyarrow as pa

from .arrow import arrow_as_array

from ..api import op, type, OpVarArgs
from ..decorator_arrow_op import arrow_op
from .. import weave_types as types
from ..ops_primitives import _dict_utils
from .. import errors
from ..language_features.tagging import (
    process_opdef_output_type,
)

from .list_ import (
    ArrowWeaveList,
    ArrowWeaveListType,
    direct_add_arrow_tags,
    vectorized_container_constructor_preprocessor,
    vectorized_input_types,
)


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
                inner_array.offsets, flattened_results
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


@arrow_op(
    name="ArrowWeaveListTypedDict-merge",
    input_type={
        "self": ArrowWeaveListType(types.TypedDict({})),
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
