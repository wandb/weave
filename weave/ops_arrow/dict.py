import pyarrow as pa
import pandas as pd

from ..api import op, type, use, OpVarArgs
from .. import weave_types as types
from ..ops_primitives import _dict_utils
from .. import errors
from ..language_features.tagging import tagged_value_type, process_opdef_output_type

from .list_ import ArrowWeaveList, ArrowWeaveListType
from .arrow import arrow_as_array, arrow_type_to_weave_type


def typeddict_pick_output_type(input_types):
    output_type = _dict_utils.typeddict_pick_output_type(input_types)
    return process_opdef_output_type.op_make_type_tagged_resolver(
        output_type,
        process_opdef_output_type.op_get_tag_type_resolver(input_types["self"]),
    )


@op(
    name="ArrowWeaveListTypedDict-pick",
    input_type={"self": ArrowWeaveListType(types.TypedDict({}))},
    output_type=lambda input_types: ArrowWeaveListType(
        typeddict_pick_output_type(
            {"self": input_types["self"].object_type, "key": input_types["key"]}
        )
    ),
)
def pick(self, key: str):
    object_type = typeddict_pick_output_type(
        {"self": self.object_type, "key": types.Const(types.String(), key)}
    )
    data = self._arrow_data
    if isinstance(self.object_type, tagged_value_type.TaggedValueType):
        data = data["_value"].combine_chunks()

    if isinstance(data, pa.StructArray):
        value = data.field(key)
    elif isinstance(self._arrow_data, pa.Table):
        value = data[key].combine_chunks()
    else:
        raise errors.WeaveTypeError(
            f"Unexpected type for pick: {type(self._arrow_data)}"
        )

    if isinstance(self.object_type, tagged_value_type.TaggedValueType):
        value = pa.Table.from_arrays(
            [self._arrow_data["_tag"], value], ["_tag", "_value"]
        )

    return ArrowWeaveList(value, object_type, self._artifact)


@op(
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
    self_keys = set(self.object_type.property_types.keys())
    other_keys = set(other.object_type.property_types.keys())
    common_keys = self_keys.intersection(other_keys)

    field_arrays: dict[str, pa.Array] = {}
    for arrow_weave_list in (self, other):
        for key in arrow_weave_list.object_type.property_types:
            if isinstance(arrow_weave_list._arrow_data, pa.Table):
                field_arrays[key] = arrow_weave_list._arrow_data[key].combine_chunks()
            else:
                field_arrays[key] = arrow_weave_list._arrow_data.field(key)

    # update field names and arrays with merged dicts

    for key in common_keys:
        if isinstance(self.object_type.property_types[key], types.TypedDict):
            self_sub_awl = ArrowWeaveList(
                self._arrow_data.field(key),
                self.object_type.property_types[key],
                self._artifact,
            )
            other_sub_awl = ArrowWeaveList(
                other._arrow_data.field(key),
                other.object_type.property_types[key],
                other._artifact,
            )
            merged = use(merge(self_sub_awl, other_sub_awl))._arrow_data  # type: ignore
            field_arrays[key] = merged

    field_names, arrays = tuple(zip(*field_arrays.items()))

    return ArrowWeaveList(
        pa.StructArray.from_arrays(arrays=arrays, names=field_names),  # type: ignore
        _dict_utils.typeddict_merge_output_type(
            {"self": self.object_type, "other": other.object_type}
        ),
        self._artifact,
    )


@op(
    name="ArrowWeaveList-vectorizedDict",
    input_type=OpVarArgs(types.Any()),
    output_type=lambda input_types: ArrowWeaveListType(
        types.TypedDict(
            {
                k: v
                if not (types.is_list_like(v) or isinstance(v, ArrowWeaveListType))
                else v.object_type
                for (k, v) in input_types.items()
            }
        )
    ),
    render_info={"type": "function"},
)
def arrow_dict_(**d):
    if len(d) == 0:
        return ArrowWeaveList(pa.array([{}]), types.TypedDict({}))
    arrays = []
    prop_types = {}
    for k, v in d.items():
        if isinstance(v, ArrowWeaveList):
            if isinstance(v.object_type, tagged_value_type.TaggedValueType):
                # We drop the tags for now :(
                # TODO: Fix
                prop_types[k] = v.object_type.value
                v = v._arrow_data["_value"]
            else:
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
    return ArrowWeaveList(table, types.TypedDict(prop_types))
