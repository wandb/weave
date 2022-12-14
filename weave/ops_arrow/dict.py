import pyarrow as pa
import pandas as pd

from ..api import op, type, use, OpVarArgs
from ..decorator_op import arrow_op
from .. import weave_types as types
from ..ops_primitives import _dict_utils
from .. import errors
from ..language_features.tagging import (
    tagged_value_type,
    process_opdef_output_type,
    tag_store,
)

from .list_ import ArrowWeaveList, ArrowWeaveListType, awl_add_arrow_tags
from .arrow import arrow_as_array


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
    prop_types: dict[str, types.Type] = {}
    for input_name, input_type in input_types.items():
        if isinstance(input_type, tagged_value_type.TaggedValueType) and (
            isinstance(input_type.value, ArrowWeaveListType)
            or types.is_list_like(input_type.value)
        ):
            outer_tag_type = input_type.tag
            object_type = input_type.value.object_type
            if isinstance(object_type, tagged_value_type.TaggedValueType):
                new_prop_type = tagged_value_type.TaggedValueType(
                    types.TypedDict(
                        {
                            **outer_tag_type.property_types,
                            **object_type.tag.property_types,
                        }
                    ),
                    object_type.value,
                )
            else:
                new_prop_type = tagged_value_type.TaggedValueType(
                    outer_tag_type, object_type
                )
            prop_types[input_name] = new_prop_type
        elif isinstance(input_type, ArrowWeaveListType) or types.is_list_like(
            input_type
        ):
            prop_types[input_name] = input_type.object_type
        else:  # is scalar
            prop_types[input_name] = input_type

    return ArrowWeaveListType(types.TypedDict(prop_types))


@op(
    name="ArrowWeaveList-vectorizedDict",
    input_type=OpVarArgs(types.Any()),
    output_type=vectorized_dict_output_type,
    render_info={"type": "function"},
)
def arrow_dict_(**d):
    if len(d) == 0:
        return ArrowWeaveList(pa.array([{}]), types.TypedDict({}))
    arrays = []
    prop_types = {}
    awl_artifact = None
    for k, v in d.items():
        if isinstance(v, ArrowWeaveList):
            if awl_artifact is None:
                awl_artifact = v._artifact
            if tag_store.is_tagged(v):
                list_tags = tag_store.get_tags(v)
                v = awl_add_arrow_tags(
                    v,
                    pa.array([list_tags] * len(v)),
                    types.TypeRegistry.type_of(list_tags),
                )
            prop_types[k] = v.object_type
            v = v._arrow_data
            arrays.append(arrow_as_array(v))
        else:
            prop_types[k] = types.TypeRegistry.type_of(v)
            arrays.append(v)

    array_lens = []
    for a, t in zip(arrays, prop_types.values()):
        if hasattr(a, "to_pylist"):
            array_lens.append(len(a))
        else:
            array_lens.append(0)
    max_len = max(array_lens)
    for l in array_lens:
        if l != 0 and l != max_len:
            raise errors.WeaveInternalError(
                f"Cannot create ArrowWeaveDict with different length arrays (scalars are ok): {array_lens}"
            )
    if max_len == 0:
        max_len = 1
    for i, (a, l) in enumerate(zip(arrays, array_lens)):
        if l == 0:
            arrays[i] = pa.array([a] * max_len)

    table = pa.Table.from_arrays(arrays, list(d.keys()))
    return ArrowWeaveList(table, types.TypedDict(prop_types), awl_artifact)
