import pyarrow as pa

from ..api import op, type, OpVarArgs
from ..decorator_op import arrow_op
from .. import weave_types as types
from ..ops_primitives import _dict_utils
from .. import errors
from ..language_features.tagging import (
    process_opdef_output_type,
)

from .list_ import (
    ArrowWeaveList,
    ArrowWeaveListType,
    vectorized_container_constructor_preprocessor,
    vectorized_input_types,
)


def typeddict_pick_output_type(input_types):
    output_type = _dict_utils.typeddict_pick_output_type(input_types)
    return process_opdef_output_type.op_make_type_tagged_resolver(
        output_type,
        process_opdef_output_type.op_get_tag_type_resolver(input_types["self"]),
    )


@arrow_op(
    name="ArrowWeaveListTypedDict-pick",
    input_type={"self": ArrowWeaveListType(types.TypedDict({})), "key": types.String()},
    output_type=lambda input_types: ArrowWeaveListType(
        typeddict_pick_output_type(
            {"self": input_types["self"].object_type, "key": input_types["key"]}
        )
    ),
)
def pick(self, key):
    object_type = typeddict_pick_output_type(
        {"self": self.object_type, "key": types.Const(types.String(), key)}
    )
    data = self._arrow_data
    if isinstance(data, pa.StructArray):
        value = data.field(key)
    elif isinstance(self._arrow_data, pa.Table):
        value = data[key].combine_chunks()
    else:
        raise errors.WeaveTypeError(
            f"Unexpected type for pick: {type(self._arrow_data)}"
        )
    return ArrowWeaveList(value, object_type, self._artifact)


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
)
def merge(self, other):

    field_arrays: dict[str, pa.Array] = {}
    for arrow_weave_list in (self, other):
        for key in arrow_weave_list.object_type.property_types:
            if isinstance(arrow_weave_list._arrow_data, pa.Table):
                field_arrays[key] = arrow_weave_list._arrow_data[key].combine_chunks()
            else:
                field_arrays[key] = arrow_weave_list._arrow_data.field(key)

    field_names, arrays = tuple(zip(*field_arrays.items()))

    return ArrowWeaveList(
        pa.StructArray.from_arrays(arrays=arrays, names=field_names),  # type: ignore
        _dict_utils.typeddict_merge_output_type(
            {"self": self.object_type, "other": other.object_type}
        ),
        self._artifact,
    )


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
