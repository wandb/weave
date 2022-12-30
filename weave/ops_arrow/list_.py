import copy
import logging
import typing
import dataclasses
import json
import numpy as np
import pandas as pd
import pyarrow as pa
from pyarrow import compute as pc


py_type = type

from ..api import op, weave_class, type, use
from ..decorator_op import arrow_op
from .. import box
from .. import weave_types as types
from .. import graph
from .. import errors
from .. import registry_mem
from .. import mappers_arrow
from .. import mappers_python_def
from .. import mappers_python
from .. import artifacts_local
from .. import storage
from .. import refs
from .. import dispatch
from .. import execute_fast
from .. import weave_internal
from .. import node_ref
from .. import context
from .. import weavify
from .. import op_args
from ..language_features.tagging import tagged_value_type, tagged_value_type_helpers
from ..language_features.tagging import process_opdef_output_type
from . import arrow
from .. import arrow_util

from ..language_features.tagging import tag_store

from . import arrow
from ..ops_primitives import list_ as base_list

from .arrow import arrow_as_array

if typing.TYPE_CHECKING:
    from .. import artifacts_local

FLATTEN_DELIMITER = "➡️"


# Temp function to handle refactor
def ArrowTableGroupByType(
    object_type: types.Type, key_type: types.Type
) -> "ArrowWeaveListType":
    return ArrowWeaveListType(ArrowTableGroupResultType(object_type, key_type))


def ArrowTableGroupResultType(
    object_type: types.Type, _key: types.Type
) -> tagged_value_type.TaggedValueType:
    return tagged_value_type.TaggedValueType(
        types.TypedDict(
            {
                "groupKey": _key,
            }
        ),
        types.List(object_type),
    )


def _recursively_flatten_structs_in_array(
    arr: pa.Array, prefix: str, _stack_depth=0
) -> dict[str, pa.Array]:
    if pa.types.is_struct(arr.type):
        result: dict[str, pa.Array] = {}
        for field in arr.type:
            new_prefix = (
                prefix + (FLATTEN_DELIMITER if _stack_depth > 0 else "") + field.name
            )
            result.update(
                _recursively_flatten_structs_in_array(
                    arr.field(field.name),
                    new_prefix,
                    _stack_depth=_stack_depth + 1,
                )
            )
        return result
    return {prefix: arr}


# TODO: make more efficient
def _unflatten_structs_in_flattened_table(table: pa.Table) -> pa.Table:
    """take a table with column names like {a.b.c: [1,2,3], a.b.d: [4,5,6], a.e: [7,8,9]}
    and return a struct array with the following structure:
    [ {a: {b: {c: 1, d: 4}, e: 7}}, {a: {b: {c: 2, d: 5}, e: 8}}, {a: {b: {c: 3, d: 6}, e: 9}} ]"""

    # get all columns in table
    column_names = list(
        map(lambda name: name.split(FLATTEN_DELIMITER), table.column_names)
    )
    multi_index = pd.MultiIndex.from_tuples(column_names)
    df = table.to_pandas()
    df.columns = multi_index
    records = df.to_dict(orient="records")

    # convert to arrow
    # records now looks like [{('a', 'b', 'c'): 1, ('a', 'b', 'd'): 2, ('a', 'e', nan): 3},
    # {('a', 'b', 'c'): 4, ('a', 'b', 'd'): 5, ('a', 'e', nan): 6},
    # {('a', 'b', 'c'): 7, ('a', 'b', 'd'): 8, ('a', 'e', nan): 9}]
    new_records = []
    for record in records:
        new_record: dict[str, typing.Any] = {}
        for entry in record:
            current_pointer = new_record
            filtered_entry = list(filter(lambda key: key is not np.nan, entry))
            for i, key in enumerate(filtered_entry):
                if key not in current_pointer and i != len(filtered_entry) - 1:
                    current_pointer[key] = {}
                elif i == len(filtered_entry) - 1:
                    current_pointer[key] = record[entry]
                current_pointer = current_pointer[key]
        new_records.append(new_record)
    rb = pa.RecordBatch.from_pylist(new_records)
    return pa.Table.from_batches([rb])


def unzip_struct_array(arr: pa.ChunkedArray) -> pa.Table:
    flattened = _recursively_flatten_structs_in_array(arr.combine_chunks(), "")
    return pa.table(flattened)


def _pick_output_type(input_types):
    if not isinstance(input_types["key"], types.Const):
        return types.UnknownType()
    key = input_types["key"].val
    prop_type = input_types["self"].object_type.property_types.get(key)
    if prop_type is None:
        return types.Invalid()
    return ArrowWeaveListType(prop_type)


def _map_each_function_type(input_types: dict[str, types.Type]) -> types.Type:
    base_op_fn_type = base_list._map_each_function_type({"arr": input_types["self"]})
    base_op_fn_type.input_types["self"] = ArrowWeaveListType(
        typing.cast(types.List, input_types["self"]).object_type
    )
    return base_op_fn_type


def _map_each_output_type(input_types: dict[str, types.Type]):
    base_output_type = base_list._map_each_output_type(
        {"arr": input_types["self"], "mapFn": input_types["map_fn"]}
    )
    return ArrowWeaveListType(base_output_type.object_type)


def _map_each(self: "ArrowWeaveList", fn):
    if types.List().assign_type(self.object_type):
        as_array = arrow_as_array(self._arrow_data)
        offsets = as_array.offsets
        flattened = as_array.flatten()
        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            new_object_type = typing.cast(
                types.List, self.object_type.value
            ).object_type
        else:
            new_object_type = typing.cast(types.List, self.object_type).object_type

        new_awl: ArrowWeaveList = ArrowWeaveList(
            flattened,
            new_object_type,
            self._artifact,
        )

        mapped = _map_each(new_awl, fn)
        reshaped_arrow_data: ArrowWeaveList = ArrowWeaveList(
            pa.ListArray.from_arrays(offsets, mapped._arrow_data),
            self.object_type,
            self._artifact,
        )

        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            return awl_add_arrow_tags(
                reshaped_arrow_data,
                self._arrow_data.field("_tag"),
                self.object_type.tag,
            )
        return reshaped_arrow_data
    return _apply_fn_node(self, fn)


def rewrite_weavelist_refs(arrow_data, object_type, artifact):
    if _object_type_has_props(object_type):
        prop_types = _object_type_prop_types(object_type)
        if isinstance(arrow_data, pa.Table):
            arrays = {}
            for col_name, col_type in prop_types.items():
                column = arrow_data[col_name]
                arrays[col_name] = rewrite_weavelist_refs(column, col_type, artifact)
            return pa.table(arrays)
        elif isinstance(arrow_data, pa.ChunkedArray):
            arrays = {}
            unchunked = arrow_data.combine_chunks()
            for col_name, col_type in prop_types.items():
                column = unchunked.field(col_name)
                arrays[col_name] = rewrite_weavelist_refs(column, col_type, artifact)
            return pa.StructArray.from_arrays(arrays.values(), names=arrays.keys())
        elif isinstance(arrow_data, pa.StructArray):
            arrays = {}
            for col_name, col_type in prop_types.items():
                column = arrow_data.field(col_name)
                arrays[col_name] = rewrite_weavelist_refs(column, col_type, artifact)
            return pa.StructArray.from_arrays(arrays.values(), names=arrays.keys())
        else:
            raise errors.WeaveTypeError('Unhandled type "%s"' % type(arrow_data))
    elif isinstance(object_type, types.UnionType):
        non_none_members = [
            m for m in object_type.members if not isinstance(m, types.NoneType)
        ]
        nullable = len(non_none_members) < len(object_type.members)
        if len(non_none_members) > 1:
            arrow_data = arrow_as_array(arrow_data)
            if not isinstance(arrow_data.type, pa.UnionType):
                raise errors.WeaveTypeError(
                    "Expected UnionType, got %s" % type(arrow_data.type)
                )
            arrays = []
            for i, _ in enumerate(arrow_data.type):
                rewritten = rewrite_weavelist_refs(
                    arrow_data.field(i),
                    non_none_members[i]
                    if not nullable
                    else types.UnionType(types.NoneType(), non_none_members[i]),
                    artifact,
                )
                arrays.append(rewritten)
            return pa.UnionArray.from_sparse(arrow_data.type_codes, arrays)
        return rewrite_weavelist_refs(arrow_data, types.non_none(object_type), artifact)
    elif _object_type_is_basic(object_type):
        return arrow_data
    elif isinstance(object_type, types.List):
        # This is a bit unfortunate that we have to loop through all the items - would be nice to do a direct memory replacement.
        return pa.array(_rewrite_pyliteral_refs(item.as_py(), object_type, artifact) for item in arrow_data)  # type: ignore

    else:
        # We have a column of refs
        new_refs = []
        for ref_str in arrow_data:
            ref_str = ref_str.as_py()
            new_refs.append(
                _rewrite_ref_entry(ref_str, object_type, artifact)
                if ref_str is not None
                else None
            )
        return pa.array(new_refs)


def _rewrite_pyliteral_refs(pyliteral_data, object_type, artifact):
    if _object_type_has_props(object_type):
        prop_types = _object_type_prop_types(object_type)
        if isinstance(pyliteral_data, dict):
            return {
                key: _rewrite_pyliteral_refs(pyliteral_data[key], value, artifact)
                for key, value in prop_types.items()
            }
        else:
            raise errors.WeaveTypeError('Unhandled type "%s"' % type(pyliteral_data))
    elif isinstance(object_type, types.UnionType):
        non_none_members = [
            m for m in object_type.members if not isinstance(m, types.NoneType)
        ]
        if len(non_none_members) > 1:
            raise errors.WeaveInternalError(
                "Unions not fully supported yet in Weave arrow"
            )
        return _rewrite_pyliteral_refs(
            pyliteral_data, types.non_none(object_type), artifact
        )
    elif _object_type_is_basic(object_type):
        return pyliteral_data
    elif isinstance(object_type, types.List):
        return [
            _rewrite_pyliteral_refs(item, object_type.object_type, artifact)
            for item in pyliteral_data
        ]
    else:
        return _rewrite_ref_entry(pyliteral_data, object_type, artifact)


def _object_type_has_props(object_type):
    return (
        isinstance(object_type, types.TypedDict)
        or isinstance(object_type, types.ObjectType)
        or isinstance(object_type, tagged_value_type.TaggedValueType)
    )


def _object_type_prop_types(object_type):
    if isinstance(object_type, tagged_value_type.TaggedValueType):
        return {
            "_tag": object_type.tag,
            "_value": object_type.value,
        }
    prop_types = object_type.property_types
    if callable(prop_types):
        prop_types = prop_types()
    return prop_types


def _object_type_is_basic(object_type):
    if isinstance(object_type, types.Const):
        object_type = object_type.val_type
    return isinstance(object_type, types.BasicType) or (
        isinstance(object_type, types.Datetime)
    )


def _rewrite_ref_entry(entry: str, object_type, artifact):
    if ":" in entry:
        return entry
    else:
        return str(refs.Ref.from_local_ref(artifact, entry, object_type).uri)


def rewrite_groupby_refs(arrow_data, group_keys, object_type, artifact):
    # TODO: Handle unions

    # hmm... we should just iterate over table columns instead!
    # This would be a nested iterate
    if isinstance(object_type, types.TypedDict) or isinstance(
        object_type, types.ObjectType
    ):
        prop_types = object_type.property_types
        if callable(prop_types):
            prop_types = prop_types()
        arrays = {}
        for group_key in group_keys:
            arrays[group_key] = arrow_data[group_key]
        for col_name, col_type in prop_types.items():
            col_name = col_name + "_list"
            column = arrow_data[col_name]
            arrays[col_name] = rewrite_groupby_refs(
                column, group_keys, col_type, artifact
            )
        return pa.table(arrays)
    elif isinstance(object_type, types.UnionType):
        if any(types.is_custom_type(m) for m in object_type.members):
            raise errors.WeaveInternalError(
                "Unions of custom types not yet support in Weave arrow"
            )
        return arrow_data
    else:
        if isinstance(object_type, types.BasicType):
            return arrow_data

        # We have a column of refs

        new_refs = []
        for ref_str_list in arrow_data:
            ref_str_list = ref_str_list.as_py()
            new_ref_str_list = []
            for ref_str in ref_str_list:
                if ":" in ref_str:
                    new_ref_str_list.append(ref_str)
                else:
                    ref = refs.LocalArtifactRef.from_local_ref(
                        artifact, ref_str, object_type
                    )
                    new_ref_str_list.append(str(ref.uri))
            new_refs.append(new_ref_str_list)
        return pa.array(new_refs)


def _arrow_sort_ranking_to_indicies(sort_ranking, col_dirs):
    flattened = sort_ranking._arrow_data_asarray_no_tags().flatten()

    columns = (
        []
    )  # this is intended to be a pylist and will be small since it is number of sort fields
    col_len = len(sort_ranking._arrow_data)
    dir_len = len(col_dirs)
    col_names = [str(i) for i in range(dir_len)]
    order = [
        (col_name, "ascending" if dir_name == "asc" else "descending")
        for col_name, dir_name in zip(col_names, col_dirs)
    ]
    # arrow data: (col_len x dir_len)
    # [
    #    [d00, d01]
    #    [d10, d11]
    #    [d20, d21]
    #    [d30, d31]
    # ]
    #
    # Flatten
    # [d00, d01, d10, d11, d20, d21, d30, d31]
    #
    # col_x = [d0x, d1x, d2x, d3x]
    # .         i * dir_len + x
    #
    #
    for i in range(dir_len):
        take_array = [j * dir_len + i for j in range(col_len)]
        columns.append(pc.take(flattened, pa.array(take_array)))
    table = pa.Table.from_arrays(columns, names=col_names)
    return pc.sort_indices(table, order)


@dataclasses.dataclass(frozen=True)
class ArrowWeaveListType(types.Type):
    _base_type = types.List()
    name = "ArrowWeaveList"

    object_type: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.object_type)

    def save_instance(self, obj, artifact, name):
        # If we are saving to the same artifact as we were written to,
        # then we don't need to rewrite any references.
        if obj._artifact == artifact:
            arrow_data = obj._arrow_data
        else:
            # super().save_instance(obj, artifact, name)
            # return
            arrow_data = rewrite_weavelist_refs(
                obj._arrow_data, obj.object_type, obj._artifact
            )

        d = {"_arrow_data": arrow_data, "object_type": obj.object_type}
        type_of_d = types.TypedDict(
            {
                "_arrow_data": types.union(
                    arrow.ArrowTableType(), arrow.ArrowArrayType()
                ),
                "object_type": types.TypeType(),
            }
        )
        if hasattr(self, "_key"):
            d["_key"] = obj._key
            type_of_d.property_types["_key"] = self._key

        serializer = mappers_python.map_to_python(type_of_d, artifact)
        result_d = serializer.apply(d)

        with artifact.new_file(f"{name}.ArrowWeaveList.json") as f:
            json.dump(result_d, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.ArrowWeaveList.json") as f:
            result = json.load(f)
        type_of_d = types.TypedDict(
            {
                "_arrow_data": types.union(
                    arrow.ArrowTableType(), arrow.ArrowArrayType()
                ),
                "object_type": types.TypeType(),
            }
        )
        if hasattr(self, "_key"):
            type_of_d.property_types["_key"] = self._key

        mapper = mappers_python.map_from_python(type_of_d, artifact)
        res = mapper.apply(result)
        return self.instance_class(artifact=artifact, **res)


ArrowWeaveListObjectTypeVar = typing.TypeVar("ArrowWeaveListObjectTypeVar")


def map_output_type(input_types):
    return ArrowWeaveListType(input_types["map_fn"].output_type)


@weave_class(weave_type=ArrowWeaveListType)
class ArrowWeaveList(typing.Generic[ArrowWeaveListObjectTypeVar]):
    _arrow_data: typing.Union[pa.Table, pa.ChunkedArray, pa.Array]
    object_type: types.Type

    def _arrow_data_asarray_no_tags(self) -> pa.Array:
        """Cast `self._arrow_data` as an array and recursively strip its tags."""

        # arrow_as_array is idempotent so even though we will hit this on every recursive call,
        # it will be a no-op after the first time.
        arrow_data = arrow_as_array(self._arrow_data)

        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            return ArrowWeaveList(
                arrow_data.field("_value"),
                self.object_type.value,
                self._artifact,
            )._arrow_data_asarray_no_tags()

        elif isinstance(self.object_type, (types.TypedDict, types.ObjectType)):
            # strip tags from each field
            arrays = []
            keys = []

            prop_types = self.object_type.property_types
            if callable(prop_types):
                prop_types = prop_types()

            for field in arrow_data.type:
                keys.append(field.name)
                arrays.append(
                    ArrowWeaveList(
                        arrow_data.field(field.name),
                        prop_types[field.name],
                        self._artifact,
                    )._arrow_data_asarray_no_tags()
                )
            return pa.StructArray.from_arrays(arrays, names=keys)

        elif isinstance(self.object_type, types.List):
            offsets = arrow_data.offsets
            # strip tags from each element
            flattened = ArrowWeaveList(
                arrow_data.flatten(),
                self.object_type.object_type,
                self._artifact,
            )._arrow_data_asarray_no_tags()

            # unflatten
            return pa.ListArray.from_arrays(offsets, flattened)

        elif isinstance(self.object_type, types.UnionType):
            is_not_simple_nullable_union = (
                len(
                    [
                        member_type
                        for member_type in self.object_type.members
                        if not types.NoneType().assign_type(member_type)
                    ]
                )
                > 1
            )

            if is_not_simple_nullable_union:
                # strip tags from each element
                if not isinstance(self._arrow_data, pa.UnionArray):
                    raise ValueError(
                        "Expected UnionArray, but got: "
                        f"{type(self._arrow_data).__name__}"
                    )
                if not isinstance(self._mapper, mappers_arrow.ArrowUnionToUnion):
                    raise ValueError(
                        "Expected ArrowUnionToUnion, but got: "
                        f"{type(self._mapper).__name__}"
                    )
                tag_stripped_members: list[pa.Array] = []
                for member_type in self.object_type.members:
                    tag_stripped_member = ArrowWeaveList(
                        self._arrow_data.field(
                            # mypy doesn't recognize that this method is inherited from the
                            # superclass of ArrowUnionToUnion
                            self._mapper.type_code_of_type(member_type)  # type: ignore
                        ),
                        member_type,
                        self._artifact,
                    )._arrow_data_asarray_no_tags()
                    tag_stripped_members.append(tag_stripped_member)
                return pa.UnionArray.from_sparse(
                    self._arrow_data.type_codes, tag_stripped_members
                )

        return arrow_data

    def __array__(self, dtype=None):
        return np.asarray(self.to_pylist())

    def __iter__(self):
        for item in self.to_pylist():
            yield self._mapper.apply(item)

    def __repr__(self):
        return f"<ArrowWeaveList: {self.object_type}>"

    def to_pylist_notags(self):
        return self._arrow_data_asarray_no_tags().to_pylist()

    def to_pylist(self):
        if isinstance(self, graph.Node):
            return []
        return self._arrow_data.to_pylist()

    # TODO: Refactor to disable None artifact? (Only used in tests)
    def __init__(self, _arrow_data, object_type=None, artifact=None) -> None:
        self._arrow_data = _arrow_data
        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._arrow_data).object_type
        self._artifact = artifact
        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)
        # TODO: construct mapper

    @op(output_type=lambda input_types: types.List(input_types["self"].object_type))
    def to_py(self):
        return list(self)

    def _count(self):
        return len(self._arrow_data)

    def __len__(self):
        return self._count()

    @op()
    def count(self) -> int:
        return self._count()

    def _get_col(self, name):
        if isinstance(self._arrow_data, pa.Table):
            col = self._arrow_data[name]
        elif isinstance(self._arrow_data, pa.ChunkedArray):
            raise NotImplementedError("TODO: implement this")
        elif isinstance(self._arrow_data, pa.StructArray):
            col = self._arrow_data.field(name)
        col_mapper = self._mapper._property_serializers[name]
        if isinstance(col_mapper, mappers_python_def.DefaultFromPy):
            return [col_mapper.apply(i.as_py()) for i in col]
        return col

    def _index(self, index):
        self._arrow_data = arrow_as_array(self._arrow_data)
        try:
            row = self._arrow_data.slice(index, 1)
        except IndexError:
            return None
        if not row:
            return None
        return mappers_arrow.map_from_arrow_scalar(
            row[0], self.object_type, self._artifact
        )

    @op(output_type=lambda input_types: input_types["self"].object_type)
    def __getitem__(self, index: int):
        return self._index(index)

    @arrow_op(
        input_type={
            "self": ArrowWeaveListType(),
            "map_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type, "index": types.Int()},
                types.Any(),
            ),
        },
        output_type=map_output_type,
    )
    def map(self, map_fn):
        return _apply_fn_node(self, map_fn)

    @arrow_op(
        name="ArrowWeaveList-mapEach",
        input_type={
            "self": ArrowWeaveListType(),
            "map_fn": _map_each_function_type,
        },
        output_type=_map_each_output_type,
    )
    def map_each(self, map_fn):
        return _map_each(self, map_fn)

    @op(
        input_type={
            "self": ArrowWeaveListType(),
            "comp_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type, "index": types.Int()},
                types.Any(),
            ),
            "col_dirs": types.List(types.String()),
        },
        output_type=lambda input_types: input_types["self"],
    )
    def sort(self, comp_fn, col_dirs):
        ranking = _apply_fn_node(self, comp_fn)
        indicies = _arrow_sort_ranking_to_indicies(ranking, col_dirs)
        return ArrowWeaveList(
            pc.take(self._arrow_data, indicies), self.object_type, self._artifact
        )

    @op(
        input_type={
            "self": ArrowWeaveListType(),
            "filter_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type, "index": types.Int()},
                types.optional(types.Boolean()),
            ),
        },
        output_type=lambda input_types: input_types["self"],
    )
    def filter(self, filter_fn):
        mask = _apply_fn_node(self, filter_fn)
        arrow_mask = mask._arrow_data_asarray_no_tags()
        return ArrowWeaveList(
            arrow_as_array(self._arrow_data).filter(arrow_mask),
            self.object_type,
            self._artifact,
        )

    @op(
        name="ArrowWeaveList-dropna",
        input_type={"self": ArrowWeaveListType()},
        output_type=lambda input_types: ArrowWeaveListType(
            types.non_none(input_types["self"].object_type)
        ),
    )
    def dropna(self):
        res = pc.drop_null(self._arrow_data)
        return ArrowWeaveList(res, types.non_none(self.object_type), self._artifact)

    def _append_column(self, name: str, data) -> "ArrowWeaveList":
        if not data:
            raise ValueError(f'Data for new column "{name}" must be nonnull.')

        if isinstance(self._arrow_data, pa.Table):
            new_data = self._arrow_data.append_column(name, [data])
        elif isinstance(self._arrow_data, pa.StructArray):
            chunked_arrays = {}
            for field in self._arrow_data.type:
                chunked_arrays[field.name] = pa.chunked_array(
                    self._arrow_data.field(field.name)
                )
            arrow_obj = pa.table(chunked_arrays)
            new_data = arrow_as_array(arrow_obj.append_column(name, [data]))
        else:
            raise ValueError(
                f"Cannot append column to {type(self._arrow_data)} object."
            )

        return ArrowWeaveList(new_data, None, self._artifact)

    def with_object_type(self, desired_type: types.Type) -> "ArrowWeaveList":
        """Converts this ArrowWeaveList into a new one with the specified object type.
        Updates the backing arrow data to also match the new type.

        If conversion is not possible, raises a ValueError.
        """
        self._arrow_data = arrow_as_array(self._arrow_data)
        mapper = mappers_arrow.map_to_arrow(desired_type, self._arrow_data)

        result: typing.Optional[ArrowWeaveList] = None

        current_type = self.object_type
        if current_type.assign_type(desired_type) and desired_type.assign_type(
            current_type
        ):
            result = self
        elif isinstance(desired_type, tagged_value_type.TaggedValueType):
            if isinstance(current_type, tagged_value_type.TaggedValueType):

                tag_awl = ArrowWeaveList(
                    self._arrow_data.field("_tag"),
                    current_type.tag,
                    self._artifact,
                ).with_object_type(desired_type.tag)

                value_awl = ArrowWeaveList(
                    self._arrow_data.field("_value"),
                    current_type.value,
                    self._artifact,
                ).with_object_type(desired_type.value)

            else:
                value_awl = self.with_object_type(desired_type.value)
                tag_array_type = mapper.result_type().field("_tag")
                tag_awl = ArrowWeaveList(
                    pa.nulls(len(value_awl), type=tag_array_type),
                    desired_type.tag,
                    self._artifact,
                )

            final_array = pa.StructArray.from_arrays(
                [tag_awl._arrow_data, value_awl._arrow_data],
                names=["_tag", "_value"],
            )

            result = ArrowWeaveList(final_array, desired_type, self._artifact)

        elif isinstance(
            current_type, tagged_value_type.TaggedValueType
        ) and not isinstance(desired_type, tagged_value_type.TaggedValueType):
            result = ArrowWeaveList(
                self._arrow_data.field("_value"), current_type.value, self._artifact
            ).with_object_type(desired_type)

        elif isinstance(desired_type, types.TypedDict):
            if isinstance(current_type, types.TypedDict):

                self_keys = set(current_type.property_types.keys())
                other_keys = set(desired_type.property_types.keys())
                common_keys = self_keys.intersection(other_keys)

                field_arrays: dict[str, pa.Array] = {}
                arrow_type = mapper.result_type()

                for key in desired_type.property_types.keys():
                    if key in common_keys:
                        field_arrays[key] = (
                            ArrowWeaveList(
                                self._arrow_data.field(key),
                                current_type.property_types[key],
                                self._artifact,
                            )
                            .with_object_type(desired_type.property_types[key])
                            ._arrow_data
                        )

                    elif key in other_keys:
                        if key not in common_keys:
                            field_arrays[key] = ArrowWeaveList(
                                pa.nulls(len(self), type=arrow_type[key].type),
                                desired_type.property_types[key],
                                self._artifact,
                            )._arrow_data

                field_names, arrays = tuple(zip(*field_arrays.items()))

                result = ArrowWeaveList(
                    pa.StructArray.from_arrays(arrays=arrays, names=field_names),  # type: ignore
                    desired_type,
                    self._artifact,
                )

        elif isinstance(desired_type, types.BasicType):
            result = ArrowWeaveList(
                self._arrow_data.cast(mapper.result_type()),
                desired_type,
                self._artifact,
            )

        elif isinstance(desired_type, types.List) and isinstance(
            current_type, types.List
        ):
            offsets = self._arrow_data.offsets
            flattened = self._arrow_data.flatten()
            flattened_converted = ArrowWeaveList(
                flattened,
                current_type.object_type,
                self._artifact,
            ).with_object_type(desired_type.object_type)

            result = ArrowWeaveList(
                pa.ListArray.from_arrays(
                    offsets, flattened_converted._arrow_data, type=mapper.result_type()
                ),
                desired_type,
                self._artifact,
            )

        elif isinstance(desired_type, types.UnionType) and desired_type.assign_type(
            current_type
        ):

            non_none_desired = types.non_none(desired_type)
            if isinstance(non_none_desired, types.UnionType):
                non_nullable_types = non_none_desired.members
            else:
                non_nullable_types = [non_none_desired]

            non_null_current_type = types.non_none(current_type)

            if len(non_nullable_types) > 1:
                type_code = mapper.type_code_of_type(non_null_current_type)

                def type_code_iterator():
                    for _ in range(len(self)):
                        yield type_code

                data_arrays: list[pa.Array] = []
                for member in non_nullable_types:
                    if member.assign_type(
                        non_null_current_type
                    ) and non_null_current_type.assign_type(member):
                        data_arrays.append(self.with_object_type(member)._arrow_data)
                    else:
                        member_mapper = mappers_arrow.map_to_arrow(
                            member, self._artifact
                        )
                        data_arrays.append(
                            pa.nulls(len(self), type=member_mapper.result_type())
                        )

                result = ArrowWeaveList(
                    pa.UnionArray.from_sparse(
                        pa.array(type_code_iterator(), type=pa.int8()),
                        data_arrays,
                    ),
                    desired_type,
                    self._artifact,
                )
            else:
                result = ArrowWeaveList(
                    self.with_object_type(non_nullable_types[0])._arrow_data,
                    desired_type,
                    self._artifact,
                )

        if result is None:
            raise ValueError(f"Cannot convert {current_type} to {desired_type}.")

        if tag_store.is_tagged(self):
            tag_store.add_tags(result, tag_store.get_tags(self))

        return result

    def concatenate(self, other: "ArrowWeaveList") -> "ArrowWeaveList":
        arrow_data = [arrow_as_array(awl._arrow_data) for awl in (self, other)]
        if arrow_data[0].type == arrow_data[1].type:
            return ArrowWeaveList(
                pa.concat_arrays(arrow_data), self.object_type, self._artifact
            )
        else:
            new_object_types_with_pushed_down_tags = [
                typing.cast(
                    ArrowWeaveListType,
                    tagged_value_type_helpers.push_down_tags_from_container_type_to_element_type(
                        types.TypeRegistry.type_of(a)
                    ),
                ).object_type
                for a in (self, other)
            ]

            new_object_type = types.merge_types(*new_object_types_with_pushed_down_tags)

            new_arrow_arrays = [
                a.with_object_type(new_object_type)._arrow_data for a in (self, other)
            ]
            return ArrowWeaveList(
                pa.concat_arrays(new_arrow_arrays), new_object_type, self._artifact
            )

    @op(
        input_type={
            "self": ArrowWeaveListType(),
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: ArrowTableGroupByType(
            input_types["self"].object_type, input_types["group_by_fn"].output_type
        ),
    )
    def groupby(self, group_by_fn):
        group_table_awl = _apply_fn_node(self, group_by_fn)
        table = self._arrow_data

        group_table = group_table_awl._arrow_data
        group_table_as_array = arrow.arrow_as_array(group_table)

        # strip tags recursively so we group on values only
        # TODO: Disable tag stripping on the group key!
        group_table_as_array_awl = ArrowWeaveList(
            group_table_as_array, group_table_awl.object_type, self._artifact
        )
        group_table_as_array_awl_stripped = (
            group_table_as_array_awl._arrow_data_asarray_no_tags()
        )

        # There was a comment that arrow doesn't allow grouping on struct columns
        # and another large block of code that tried to avoid passing in a struct column.
        # But that code was actually never executing due to a bug.
        # TODO: investigate and fix this (do we really need unzip_struct_array?)
        if isinstance(
            group_table_as_array_awl_stripped,
            (pa.ChunkedArray, pa.Array, pa.StructArray),
        ):
            if isinstance(group_table_as_array_awl_stripped, pa.ChunkedArray):
                group_table_as_array_awl_stripped_combined = (
                    group_table_as_array_awl_stripped.combine_chunks()
                )
            else:
                group_table_as_array_awl_stripped_combined = (
                    group_table_as_array_awl_stripped
                )

            group_table_chunked = pa.chunked_array(
                pa.StructArray.from_arrays(
                    [
                        group_table_as_array_awl_stripped_combined,
                    ],
                    names=["group_key"],
                )
            )
            group_table_chunked_unzipped = unzip_struct_array(group_table_chunked)
            group_cols = group_table_chunked_unzipped.column_names
        else:
            raise errors.WeaveInternalError(
                "Arrow groupby not yet support for map result: %s"
                % type(group_table_as_array_awl)
            )

        # Serializing a large arrow table and then reading it back
        # causes it to come back with more than 1 chunk. It seems the aggregation
        # operations don't like this. It will raise a cryptic error about
        # ExecBatches need to have the same link without this combine_chunks line
        # But combine_chunks doesn't seem like the most efficient thing to do
        # either, since it'll have to concatenate everything together.
        # But this fixes the crash for now!
        # TODO: investigate this as we optimize the arrow implementation
        group_table_combined = group_table_chunked_unzipped.combine_chunks()

        group_table_combined_indexed = group_table_combined.append_column(
            "_index", pa.array(np.arange(len(group_table_combined)))
        )
        awl_grouped = group_table_combined_indexed.group_by(group_cols)
        awl_grouped_agg = awl_grouped.aggregate([("_index", "list")])
        awl_grouped_agg_struct = _unflatten_structs_in_flattened_table(awl_grouped_agg)

        combined = awl_grouped_agg_struct.column("_index_list").combine_chunks()
        grouped_keys = awl_grouped_agg_struct.column("group_key").combine_chunks()
        nested_group_keys = pa.StructArray.from_arrays(
            [grouped_keys], names=["groupKey"]
        )

        val_lengths = combined.value_lengths()
        flattened_indexes = combined.flatten()
        values = arrow.arrow_as_array(table).take(flattened_indexes)
        offsets = np.cumsum(np.concatenate(([0], val_lengths)))
        grouped_results = pa.ListArray.from_arrays(offsets, values)
        grouped_awl = ArrowWeaveList(
            grouped_results, types.List(self.object_type), self._artifact
        )

        return awl_add_arrow_tags(
            grouped_awl,
            nested_group_keys,
            types.TypedDict({"groupKey": group_table_awl.object_type}),
        )

    @op(output_type=lambda input_types: input_types["self"])
    def offset(self, offset: int):
        return ArrowWeaveList(
            self._arrow_data.slice(offset), self.object_type, self._artifact
        )

    def _limit(self, limit: int):
        return ArrowWeaveList(
            self._arrow_data.slice(0, limit), self.object_type, self._artifact
        )

    @op(output_type=lambda input_types: input_types["self"])
    def limit(self, limit: int):
        return self._limit(limit)

    @op(
        input_type={"self": ArrowWeaveListType(types.TypedDict({}))},
        output_type=lambda input_types: ArrowWeaveListType(
            types.TypedDict(
                {
                    k: v
                    if not (types.is_list_like(v) or isinstance(v, ArrowWeaveListType))
                    else v.object_type
                    for (k, v) in input_types["self"].object_type.property_types.items()
                }
            )
        ),
    )
    def unnest(self):
        if not self or not isinstance(self.object_type, types.TypedDict):
            return self

        list_cols = []
        for k, v_type in self.object_type.property_types.items():
            if types.is_list_like(v_type):
                list_cols.append(k)
        if not list_cols:
            return self

        if isinstance(self._arrow_data, pa.StructArray):
            rb = pa.RecordBatch.from_struct_array(
                self._arrow_data
            )  # this pivots to columnar layout
            arrow_obj = pa.Table.from_batches([rb])
        else:
            arrow_obj = self._arrow_data

        # todo: make this more efficient. we shouldn't have to convert back and forth
        # from the arrow in-memory representation to pandas just to call the explode
        # function. but there is no native pyarrow implementation of this
        return pa.Table.from_pandas(
            df=arrow_obj.to_pandas().explode(list_cols), preserve_index=False
        )


def _apply_fn_node(awl: ArrowWeaveList, fn: graph.OutputNode) -> ArrowWeaveList:
    vectorized_fn = vectorize(fn)
    index_awl: ArrowWeaveList[int] = ArrowWeaveList(pa.array(np.arange(len(awl))))
    row_type = ArrowWeaveListType(awl.object_type)
    fn_res_node = weave_internal.call_fn(
        vectorized_fn,
        {
            "row": weave_internal.make_const_node(row_type, awl),
            "index": weave_internal.make_const_node(
                types.TypeRegistry.type_of(index_awl), index_awl._arrow_data
            ),
        },
    )

    res = use(fn_res_node)

    # Since it is possible that the result of `use` bails out of arrow due to a
    # mismatch in the types / op support. This is most likely due to gap in the
    # implementation of vectorized ops. However, there are cases where it is
    # currently expected - for example calling a custom op on a custom type. An
    # example of this is in `ops_arrow/test_arrow.py::test_custom_types_tagged`:
    #
    #     ` data_node.map(lambda row: row["im"].width_())`
    #
    # If such cases did not exist, then we should probably raise in this case.
    # However, for now, we will just convert the result back to arrow if it is a
    # list.
    if not isinstance(res, ArrowWeaveList):
        err_msg = f"Applying vectorized function {fn} to awl of {awl.object_type} \
            resulted in a non vectorized result type: {py_type(res)}. This likely \
            means 1 or more ops in the function were converted to the list \
            implementation in compile."
        if isinstance(res, list):
            res = to_arrow(res)
            logging.error(err_msg)
        else:
            raise errors.WeaveVectorizationError(err_msg)

    return res


def pushdown_list_tags(arr: ArrowWeaveList) -> ArrowWeaveList:

    if tag_store.is_tagged(arr):
        tag = tag_store.get_tags(arr)
        tag_type = types.TypeRegistry.type_of(tag)
        tags: ArrowWeaveList = to_arrow([tag] * len(arr))
        return awl_add_arrow_tags(arr, tags._arrow_data, tag_type)
    return arr


ArrowWeaveListType.instance_classes = ArrowWeaveList
ArrowWeaveListType.instance_class = ArrowWeaveList


def awl_object_type_with_index(object_type):
    return tagged_value_type.TaggedValueType(
        types.TypedDict({"indexCheckpoint": types.Int()}), object_type
    )


def arrow_weave_list_createindexcheckpoint_output_type(input_type):
    return ArrowWeaveListType(awl_object_type_with_index(input_type["arr"].object_type))


@op(
    name="arrowWeaveList-createIndexCheckpointTag",
    input_type={"arr": ArrowWeaveListType(types.Any())},
    output_type=arrow_weave_list_createindexcheckpoint_output_type,
)
def arrow_weave_list_createindexCheckpoint(arr):
    # Tags are always stored as a list of dicts, even if there is only one tag
    tag_array = pa.StructArray.from_arrays(
        [pa.array(np.arange(len(arr._arrow_data)))],
        names=["indexCheckpoint"],
    )
    return awl_add_arrow_tags(
        arr,
        tag_array,
        types.TypedDict({"indexCheckpoint": types.Int()}),
    )


def _concat_output_type(input_types: typing.Dict[str, types.List]) -> types.Type:
    arr_type: types.List = input_types["arr"]
    inner_type = types.non_none(arr_type.object_type)

    if isinstance(inner_type, types.UnionType):
        if not all(types.is_list_like(t) for t in inner_type.members):
            raise ValueError(
                "opConcat: expected all members of inner type to be list-like"
            )

        new_union_members = [
            typing.cast(
                ArrowWeaveListType,
                tagged_value_type_helpers.push_down_tags_from_container_type_to_element_type(
                    t
                ),
            ).object_type
            for t in inner_type.members
        ]

        # merge the types into a single type
        new_inner_type = new_union_members[0]
        for t in new_union_members[1:]:
            new_inner_type = types.merge_types(new_inner_type, t)

        return ArrowWeaveListType(new_inner_type)

    elif isinstance(inner_type, tagged_value_type.TaggedValueType):
        inner_type_value = inner_type.value
        inner_type_tag = inner_type.tag
        inner_type_value_inner_type = typing.cast(
            ArrowWeaveListType, inner_type_value
        ).object_type

        return ArrowWeaveListType(
            tagged_value_type.TaggedValueType(
                inner_type_tag, inner_type_value_inner_type
            )
        )

    return inner_type


@op(
    name="ArrowWeaveList-concat",
    input_type={
        "arr": types.List(
            types.union(types.NoneType(), ArrowWeaveListType(types.Any()))
        )
    },
    output_type=_concat_output_type,
)
def concat(arr):
    arr = [item for item in arr if item != None]

    if len(arr) == 0:
        return to_arrow([])
    elif len(arr) == 1:
        return arr[0]

    res = arr[0]
    res = typing.cast(ArrowWeaveList, res)
    res = pushdown_list_tags(res)

    for i in range(1, len(arr)):
        tagged = pushdown_list_tags(arr[i])
        res = res.concatenate(tagged)
    return res


class VectorizeError(errors.WeaveBaseError):
    pass


def make_vectorized_object_constructor(constructor_op_name: str) -> None:
    constructor_op = registry_mem.memory_registry.get_op(constructor_op_name)
    if callable(constructor_op.raw_output_type):
        raise errors.WeaveInternalError(
            "Unexpected. All object type constructors have fixed return types."
        )

    type_name = constructor_op.raw_output_type.name
    vectorized_constructor_op_name = f'ArrowWeaveList-{type_name.replace("-", "_")}'
    if registry_mem.memory_registry.have_op(vectorized_constructor_op_name):
        return

    output_type = ArrowWeaveListType(constructor_op.raw_output_type)

    @op(
        name=vectorized_constructor_op_name,
        input_type={
            "attributes": ArrowWeaveListType(
                constructor_op.input_type.weave_type().property_types["attributes"]  # type: ignore
            )
        },
        output_type=output_type,
        render_info={"type": "function"},
    )
    def vectorized_constructor(attributes):
        if callable(output_type):
            ot = output_type({"attributes": types.TypeRegistry.type_of(attributes)})
        else:
            ot = output_type
        return ArrowWeaveList(
            attributes._arrow_data, ot.object_type, attributes._artifact
        )


def vectorize(
    weave_fn,
    with_respect_to: typing.Optional[typing.Iterable[graph.VarNode]] = None,
    stack_depth: int = 0,
):
    """Convert a Weave Function of T to a Weave Function of ArrowWeaveList[T]

    We walk the DAG represented by weave_fn, starting from its roots. Replace
    with_respect_to VarNodes of Type T with ArrowWeaveList[T]. Then as we
    walk up the DAG, replace OutputNodes with new op calls to whatever ops
    exist that can handle the changed input types.
    """

    # TODO: handle with_respect_to, it doesn't do anything right now.

    if stack_depth > 10:
        raise VectorizeError("Vectorize recursion depth exceeded")

    def ensure_object_constructors_created(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            if node.from_op.name.startswith("objectConstructor-"):
                make_vectorized_object_constructor(node.from_op.name)
        return node

    def expand_nodes(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            inputs = node.from_op.inputs
            if node.from_op.name == "number-pybin":
                bin_fn = weave_internal.use(inputs["bin_fn"])
                in_ = inputs["in_"]
                return weave_internal.call_fn(bin_fn, {"row": in_})  # type: ignore
        return node

    def convert_node(node):
        if isinstance(node, graph.OutputNode):
            inputs = node.from_op.inputs
            first_input_name, first_input_node = list(inputs.items())[0]
            # since dict takes OpVarArgs(typing.Any()) as input, it will always show up
            # as a candidate for vectorizing itself. We don't want to do that, so we
            # explicitly force using ArrowWeaveList-dict instead.
            if (
                node.from_op.name.endswith("map")
                or node.from_op.name.endswith("groupby")
                or node.from_op.name.endswith("filter")
                or node.from_op.name.endswith("sort")
            ) and ArrowWeaveListType().assign_type(first_input_node.type):
                # Here, we are in a situation where we are attempting to vectorize a lambda function. THis
                # is a bit tricky, because these operations can only be applied on the outermost layer. Therefore
                # we need to bail out to the non-vectorized version
                # raise errors.WeaveVectorizationError("Cannot vectorize lambda functions")
                name = node.from_op.name.split("-")[-1]
                op = registry_mem.memory_registry.get_op(name)
                map_op = registry_mem.memory_registry.get_op("map")
                first_input_node_as_list = ArrowWeaveList.to_py(
                    first_input_node
                )  # op to eject to py
                input_copy = inputs.copy()
                input_copy[first_input_name] = first_input_node_as_list
                res = map_op.lazy_call(
                    **{
                        "arr": first_input_node_as_list,
                        "mapFn": graph.ConstNode(
                            types.Function(
                                {"row": first_input_node_as_list.type.object_type},
                                node.type,
                            ),
                            op.lazy_call(*input_copy.values()),
                        ),
                    }
                )
                return res
            if node.from_op.name == "dict":
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveList-vectorizedDict"
                )
                return op.lazy_call(**inputs)
            if node.from_op.name == "list":
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveList-vectorizedList"
                )
                return op.lazy_call(**inputs)
            elif node.from_op.name == "Object-__getattr__":
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveListObject-__vectorizedGetattr__"
                )
                return op.lazy_call(**inputs)
            else:
                # Get a version of op that can handle vectorized (ArrowWeaveList) inputs
                op = dispatch.get_op_for_input_types(
                    node.from_op.name, [], {k: v.type for k, v in inputs.items()}
                )
                if (
                    op
                    and isinstance(op.input_type, op_args.OpNamedArgs)
                    and isinstance(
                        list(op.input_type.arg_types.values())[0], ArrowWeaveListType
                    )
                ):
                    # We have a vectorized implementation of this op already.
                    final_inputs = {
                        k: v for k, v in zip(op.input_type.arg_types, inputs.values())
                    }
                    return op.lazy_call(**final_inputs)
                # see if weave function can be expanded and vectorized
                op_def = registry_mem.memory_registry.get_op(node.from_op.name)
                if op_def.weave_fn is None:
                    # this could raise
                    try:
                        op_def.weave_fn = weavify.op_to_weave_fn(op_def)
                    except (errors.WeavifyError, errors.WeaveDispatchError):
                        pass
                if op_def.weave_fn is not None:
                    vectorized = vectorize(op_def.weave_fn, stack_depth=stack_depth + 1)
                    return weave_internal.call_fn(vectorized, inputs)
                else:
                    # No weave_fn, so we can't vectorize this op. Just
                    # use map
                    input0_name, input0_val = list(inputs.items())[0]
                    if isinstance(input0_val, ArrowWeaveList):
                        py_node = input0_val.to_py()
                        new_inputs = {input0_name: py_node}
                        for k, v in list(inputs.items())[1:]:
                            new_inputs[k] = v
                    else:
                        new_inputs = inputs
                    op = dispatch.get_op_for_input_types(
                        node.from_op.name,
                        [],
                        {k: v.type for k, v in new_inputs.items()},
                    )
                    if op is None:
                        raise VectorizeError(
                            "No fallback mapped op found for: %s" % node.from_op.name
                        )
                    return op.lazy_call(**new_inputs)
        elif isinstance(node, graph.VarNode):
            # Vectorize variable
            # NOTE: This is the only line that is specific to the arrow
            #     implementation (uses ArrowWeaveListType). Everything
            #     else will work for other List types, as long as there is
            #     a set of ops declared that can handle the new types.
            if with_respect_to is None or any(
                node is wrt_node for wrt_node in with_respect_to
            ):
                return graph.VarNode(ArrowWeaveListType(node.type), node.name)
            return node
        elif isinstance(node, graph.ConstNode):
            return node

    weave_fn = graph.map_nodes_top_level(
        [weave_fn], ensure_object_constructors_created
    )[0]
    weave_fn = graph.map_nodes_top_level([weave_fn], expand_nodes)[0]
    return graph.map_nodes_top_level([weave_fn], convert_node)[0]


def dataframe_to_arrow(df):
    return ArrowWeaveList(pa.Table.from_pandas(df))


def recursively_merge_union_types_if_they_are_unions_of_structs(
    type_: types.Type,
) -> types.Type:
    """Input preprocessor for to_arrow()."""
    if isinstance(type_, types.TypedDict):
        return types.TypedDict(
            {
                k: recursively_merge_union_types_if_they_are_unions_of_structs(v)
                for k, v in type_.property_types.items()
            }
        )
    elif isinstance(type_, types.UnionType):
        if type_.is_simple_nullable() or len(type_.members) < 2:
            return type_

        new_type = type_.members[0]
        for member in type_.members[1:]:
            new_type = types.merge_types(new_type, member)

        if isinstance(new_type, types.UnionType):
            # cant go down any further
            return new_type

        return recursively_merge_union_types_if_they_are_unions_of_structs(new_type)

    elif isinstance(type_, types.List):
        return types.List(
            recursively_merge_union_types_if_they_are_unions_of_structs(
                type_.object_type
            )
        )
    elif isinstance(type_, ArrowWeaveListType):
        return ArrowWeaveListType(
            recursively_merge_union_types_if_they_are_unions_of_structs(
                type_.object_type
            )
        )
    elif isinstance(type_, tagged_value_type.TaggedValueType):
        return tagged_value_type.TaggedValueType(
            typing.cast(
                types.TypedDict,
                recursively_merge_union_types_if_they_are_unions_of_structs(type_.tag),
            ),
            recursively_merge_union_types_if_they_are_unions_of_structs(type_.value),
        )

    return type_


def recursively_build_pyarrow_array(
    py_objs: list[typing.Any],
    pyarrow_type: pa.DataType,
    mapper,
    py_objs_already_mapped: bool = False,
) -> pa.Array:
    arrays: list[pa.Array] = []
    if isinstance(mapper.type, types.UnionType) and mapper.type.is_simple_nullable():
        nonnull_mapper = [
            m for m in mapper._member_mappers if m.type != types.NoneType()
        ][0]
        return recursively_build_pyarrow_array(
            py_objs, pyarrow_type, nonnull_mapper, py_objs_already_mapped
        )
    if pa.types.is_struct(pyarrow_type):
        keys: list[str] = []
        assert isinstance(
            mapper,
            (
                mappers_arrow.TypedDictToArrowStruct,
                mappers_arrow.TaggedValueToArrowStruct,
                mappers_arrow.ObjectToArrowStruct,
            ),
        )
        for field in pyarrow_type:

            if isinstance(
                mapper,
                mappers_arrow.TypedDictToArrowStruct,
            ):
                array = recursively_build_pyarrow_array(
                    [
                        py_obj.get(field.name, None) if py_obj is not None else None
                        for py_obj in py_objs
                    ],
                    field.type,
                    mapper._property_serializers[field.name],
                    py_objs_already_mapped,
                )
            if isinstance(
                mapper,
                mappers_arrow.ObjectToArrowStruct,
            ):
                data: list[typing.Any] = []
                for py_obj in py_objs:
                    if py_obj is None:
                        data.append(None)
                    elif py_objs_already_mapped:
                        data.append(py_obj.get(field.name, None))
                    else:
                        data.append(getattr(py_obj, field.name, None))

                array = recursively_build_pyarrow_array(
                    data,
                    field.type,
                    mapper._property_serializers[field.name],
                    py_objs_already_mapped,
                )

            elif isinstance(mapper, mappers_arrow.TaggedValueToArrowStruct):
                if field.name == "_tag":
                    array = recursively_build_pyarrow_array(
                        [tag_store.get_tags(py_obj) for py_obj in py_objs],
                        field.type,
                        mapper._tag_serializer,
                        py_objs_already_mapped,
                    )
                else:
                    array = recursively_build_pyarrow_array(
                        [py_obj for py_obj in py_objs],
                        field.type,
                        mapper._value_serializer,
                        py_objs_already_mapped,
                    )

            arrays.append(array)
            keys.append(field.name)
        return pa.StructArray.from_arrays(arrays, keys)
    elif pa.types.is_union(pyarrow_type):
        assert isinstance(mapper, mappers_arrow.UnionToArrowUnion)
        type_codes: list[int] = [mapper.type_code_of_obj(o) for o in py_objs]
        for type_code, field in enumerate(pyarrow_type):
            array = recursively_build_pyarrow_array(
                [
                    py_obj if type_codes[i] == type_code else None
                    for i, py_obj in enumerate(py_objs)
                ],
                field.type,
                mapper._member_mappers[type_code],
            )
            arrays.append(array)
        return pa.UnionArray.from_sparse(
            pa.array(type_codes, type=pa.int8()),
            arrays,
        )
    return pa.array(
        (mapper.apply(o) for o in py_objs) if not py_objs_already_mapped else py_objs,
        pyarrow_type,
    )


# This will be a faster version fo to_arrow (below). Its
# used in op file-table, to convert from a wandb Table to Weave
# (that code is very experimental and not totally working yet)
def to_arrow_from_list_and_artifact(obj, object_type, artifact):
    # Get what the parquet type will be.
    merged_object_type = recursively_merge_union_types_if_they_are_unions_of_structs(
        object_type
    )
    mapper = mappers_arrow.map_to_arrow(merged_object_type, artifact)
    pyarrow_type = mapper.result_type()

    arrow_obj = recursively_build_pyarrow_array(
        obj, pyarrow_type, mapper, py_objs_already_mapped=True
    )
    weave_obj = ArrowWeaveList(arrow_obj, merged_object_type, artifact)

    return weave_obj


def to_arrow(obj, wb_type=None):
    if wb_type is None:
        wb_type = types.TypeRegistry.type_of(obj)
    artifact = artifacts_local.LocalArtifact("to-arrow-%s" % wb_type.name)
    outer_tags: typing.Optional[dict[str, typing.Any]] = None
    if isinstance(wb_type, tagged_value_type.TaggedValueType):
        outer_tags = tag_store.get_tags(obj)
        wb_type = wb_type.value
    if isinstance(wb_type, types.List):
        merged_object_type = (
            recursively_merge_union_types_if_they_are_unions_of_structs(
                wb_type.object_type
            )
        )

        # Convert to arrow, serializing Custom objects to the artifact
        mapper = mappers_arrow.map_to_arrow(merged_object_type, artifact)
        pyarrow_type = arrow_util.arrow_type(mapper.result_type())
        # py_objs = (mapper.apply(o) for o in obj)
        # TODO: do I need this branch? Does it work now?
        # if isinstance(wb_type.object_type, types.ObjectType):
        #     arrow_obj = pa.array(py_objs, pyarrow_type)

        arrow_obj = recursively_build_pyarrow_array(obj, pyarrow_type, mapper)
        weave_obj = ArrowWeaveList(arrow_obj, merged_object_type, artifact)

        # Save the weave object to the artifact
        ref = storage.save(weave_obj, artifact=artifact)
        if outer_tags is not None:
            tag_store.add_tags(ref.obj, outer_tags)

        return ref.obj

    raise errors.WeaveInternalError("to_arrow not implemented for: %s" % obj)


def awl_add_arrow_tags(
    l: ArrowWeaveList, arrow_tags: pa.StructArray, tag_type: types.Type
):
    # get current tags
    data = l._arrow_data
    current_tags = None
    if isinstance(data, pa.Table):
        if "_tag" in data.column_names:
            current_tags = data["_tag"].combine_chunks()
    elif isinstance(data, pa.StructArray):
        if data.type.get_field_index("_tag") > -1:
            current_tags = data.field("_tag")
    if current_tags is None:
        tag_arrays = []
        tag_names = []
    else:
        tag_arrays = [current_tags.field(f.name) for f in current_tags.type]
        tag_names = [f.name for f in current_tags.type]

    for tag_field in arrow_tags.type:
        if tag_field.name in tag_names:
            existing_index = tag_names.index(tag_field.name)
            tag_arrays[existing_index] = arrow_tags.field(tag_field.name)
        else:
            tag_arrays.append(arrow_tags.field(tag_field.name))
            tag_names.append(tag_field.name)

    tag_array = pa.StructArray.from_arrays(
        tag_arrays,
        tag_names,
    )
    if isinstance(l._arrow_data, pa.Table):
        if isinstance(l.object_type, tagged_value_type.TaggedValueType):
            new_value = l._arrow_data["_value"]
        else:
            new_value = pa.StructArray.from_arrays(
                # TODO: we shouldn't need to combine chunks, we can produce this in the
                # original chunked form for zero copy
                [c.combine_chunks() for c in l._arrow_data.columns],
                names=l._arrow_data.column_names,
            )
    elif isinstance(l._arrow_data, pa.StructArray):
        if isinstance(l.object_type, tagged_value_type.TaggedValueType):
            new_value = l._arrow_data.field("_value")
        else:
            new_value = l._arrow_data
    else:
        # Else its an arrow array
        new_value = l._arrow_data
    new_value = pa.StructArray.from_arrays([tag_array, new_value], ["_tag", "_value"])

    new_object_type = process_opdef_output_type.op_make_type_tagged_resolver(
        l.object_type, tag_type
    )

    return ArrowWeaveList(new_value, new_object_type, l._artifact)


def vectorized_input_types(input_types: dict[str, types.Type]) -> dict[str, types.Type]:
    prop_types: dict[str, types.Type] = {}
    for input_name, input_type in input_types.items():
        if isinstance(input_type, types.Const):
            input_type = input_type.val_type
        if isinstance(input_type, tagged_value_type.TaggedValueType) and (
            isinstance(input_type.value, ArrowWeaveListType)
            or types.is_list_like(input_type.value)
        ):
            outer_tag_type = input_type.tag
            object_type = input_type.value.object_type  # type: ignore
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
            prop_types[input_name] = input_type.object_type  # type: ignore
        else:  # is scalar
            prop_types[input_name] = input_type
    return prop_types


@dataclasses.dataclass
class VectorizedContainerConstructorResults:
    arrays: list[pa.Array]
    prop_types: dict[str, types.Type]
    max_len: int
    artifact: typing.Optional["artifacts_local.Artifact"]


def vectorized_container_constructor_preprocessor(
    input_dict: dict[str, typing.Any]
) -> VectorizedContainerConstructorResults:
    if len(input_dict) == 0:
        return VectorizedContainerConstructorResults([], {}, 0, None)
    arrays = []
    prop_types = {}
    awl_artifact = None
    for k, v in input_dict.items():
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

    return VectorizedContainerConstructorResults(
        arrays, prop_types, max_len, awl_artifact
    )


def vectorized_list_output_type(input_types):
    element_types = vectorized_input_types(input_types).values()
    return ArrowWeaveListType(types.List(types.union(*element_types)))


@op(
    name="ArrowWeaveList-vectorizedList",
    input_type=op_args.OpVarArgs(types.Any()),
    output_type=vectorized_list_output_type,
    render_info={"type": "function"},
)
def arrow_list_(**e):
    res = vectorized_container_constructor_preprocessor(e)
    element_types = res.prop_types.values()
    concatted = pa.concat_arrays(res.arrays)
    take_ndxs = []
    for row_ndx in range(res.max_len):
        take_ndxs.extend([row_ndx + i * res.max_len for i in range(len(e))])
    values = concatted.take(pa.array(take_ndxs))
    offsets = pa.array(
        [i * len(e) for i in range(res.max_len)] + [res.max_len * len(e)]
    )
    return ArrowWeaveList(
        pa.ListArray.from_arrays(offsets, values),
        types.List(types.union(*element_types)),
        res.artifact,
    )
