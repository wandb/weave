import typing

import dataclasses
import pyarrow as pa
import pandas as pd

from ..api import op, weave_class, type, use, OpVarArgs
from .. import weave_types as types
from ..ops_primitives import _dict_utils
from .. import errors

from .list_ import ArrowWeaveList, ArrowWeaveListType


@dataclasses.dataclass(frozen=True)
class ArrowWeaveListTypedDictType(ArrowWeaveListType):
    # TODO: This should not be assignable via constructor. It should be
    #    a static property type at this point.
    object_type: types.Type = types.TypedDict({})


@weave_class(weave_type=ArrowWeaveListTypedDictType)
class ArrowWeaveListTypedDict(ArrowWeaveList):
    object_type = types.TypedDict({})
    _arrow_data: typing.Union[pa.StructArray, pa.Table]

    @op(
        name="ArrowWeaveListTypedDict-pick",
        output_type=lambda input_types: ArrowWeaveListType(
            _dict_utils.typeddict_pick_output_type(
                {"self": input_types["self"].object_type, "key": input_types["key"]}
            )
        ),
    )
    def pick(self, key: str):
        object_type = _dict_utils.typeddict_pick_output_type(
            {"self": self.object_type, "key": types.Const(types.String(), key)}
        )
        if isinstance(self._arrow_data, pa.StructArray):
            return ArrowWeaveList(
                self._arrow_data.field(key), object_type, self._artifact
            )
        elif isinstance(self._arrow_data, pa.Table):
            return ArrowWeaveList(
                self._arrow_data[key].combine_chunks(), object_type, self._artifact
            )
        else:
            raise errors.WeaveTypeError(
                f"Unexpected type for pick: {type(self._arrow_data)}"
            )

    @op(
        name="ArrowWeaveListTypedDict-merge",
        input_type={
            "self": ArrowWeaveListTypedDictType(),
            "other": ArrowWeaveListTypedDictType(),
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

        field_names_to_arrays: dict[str, pa.Array] = {
            key: arrow_weave_list._arrow_data.field(key)
            for arrow_weave_list in (self, other)
            for key in arrow_weave_list.object_type.property_types
        }

        # update field names and arrays with merged dicts

        for key in common_keys:
            if isinstance(self.object_type.property_types[key], types.TypedDict):
                self_sub_awl = ArrowWeaveList(
                    self._arrow_data.field(key), self.object_type.property_types[key]
                )
                other_sub_awl = ArrowWeaveList(
                    other._arrow_data.field(key), other.object_type.property_types[key]
                )
                merged = use(ArrowWeaveListTypedDict.merge(self_sub_awl, other_sub_awl))._arrow_data  # type: ignore
                field_names_to_arrays[key] = merged

        field_names, arrays = tuple(zip(*field_names_to_arrays.items()))

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
    unwrapped_dict = {
        k: v if not isinstance(v, ArrowWeaveList) else v._arrow_data
        for k, v in d.items()
    }
    table = pa.Table.from_pandas(df=pd.DataFrame(unwrapped_dict), preserve_index=False)
    batch = table.to_batches()[0]
    names = batch.schema.names
    arrays = batch.columns
    struct_array = pa.StructArray.from_arrays(arrays, names=names)
    return ArrowWeaveList(struct_array)
