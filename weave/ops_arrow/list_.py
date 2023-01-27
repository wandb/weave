import json
import logging
import typing
import contextlib
import dataclasses
import numpy as np
import pyarrow as pa
from pyarrow import compute as pc
from collections import defaultdict
import duckdb

py_type = type

from ..api import op, weave_class, type, use
from .. import weave_types as types
from .. import box
from .. import graph
from .. import errors
from .. import registry_mem
from .. import mappers_arrow
from .. import mappers_python_def
from .. import artifact_mem
from .. import op_def
from .. import storage
from .. import dispatch
from .. import weave_internal
from .. import weavify
from .. import op_args
from ..language_features.tagging import tagged_value_type, tagged_value_type_helpers
from ..language_features.tagging import process_opdef_output_type
from . import arrow
from .. import arrow_util

from ..language_features.tagging import tag_store
from ..ops_primitives import list_ as base_list

from .arrow import arrow_as_array, ArrowWeaveListType
from .. import artifact_base

FLATTEN_DELIMITER = "➡️"

NestedTableColumns = dict[str, typing.Union[dict, pa.ChunkedArray]]


@contextlib.contextmanager
def duckdb_con() -> typing.Generator[duckdb.DuckDBPyConnection, None, None]:
    con = duckdb.connect()
    try:
        yield con
    finally:
        con.close()


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


def _unflatten_structs_in_flattened_table(table: pa.Table) -> pa.Table:
    """take a table with column names like {a.b.c: [1,2,3], a.b.d: [4,5,6], a.e: [7,8,9]}
    and return a struct array with the following structure:
    [ {a: {b: {c: 1, d: 4}, e: 7}}, {a: {b: {c: 2, d: 5}, e: 8}}, {a: {b: {c: 3, d: 6}, e: 9}} ]"""

    def recursively_build_nested_struct_array(
        columns: dict[str, pa.Array]
    ) -> pa.StructArray:
        result: NestedTableColumns = defaultdict(lambda: {})
        for colname in columns:
            spl_colname = colname.split(FLATTEN_DELIMITER)
            prefix = spl_colname[0]
            suffix = FLATTEN_DELIMITER.join(spl_colname[1:])
            if suffix:
                result[prefix][suffix] = columns[colname]
            else:
                result[prefix] = columns[colname]

        for colname in result:
            if isinstance(result[colname], dict):
                result[colname] = recursively_build_nested_struct_array(result[colname])

        names: list[str] = []
        arrays: list[pa.ChunkedArray] = []

        for name, array in result.items():
            names.append(name)
            arrays.append(array)

        return pa.StructArray.from_arrays(arrays, names)

    recurse_input = {
        colname: table[colname].combine_chunks() for colname in table.column_names
    }

    sa = recursively_build_nested_struct_array(recurse_input)

    names: list[str] = []
    chunked_arrays: list[pa.ChunkedArray] = []

    for field in sa.type:
        names.append(field.name)
        chunked_arrays.append(pa.chunked_array(sa.field(field.name)))

    return pa.Table.from_arrays(chunked_arrays, names=names)


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
        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            as_array = as_array.field("_value")

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
                    ref = artifact.from_local_ref_str(ref_str, object_type)
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


def _slow_arrow_or_list_ranking(
    awl_or_list: typing.Union["ArrowWeaveList", list], col_dirs
):
    # This function is used to handle cases where the sort function will not play nicely with AWL
    if isinstance(awl_or_list, ArrowWeaveList):
        awl_or_list = awl_or_list.to_pylist_notags()
    py_columns: dict[str, list] = {}
    for row in awl_or_list:
        for col_ndx, cell in enumerate(row):
            col_name = f"c_{col_ndx}"
            if col_name not in py_columns:
                py_columns[col_name] = []
            if not isinstance(cell, (str, int, float)):
                # This is the crazy line - we need to convert it to something sane
                # Maybe there is a generic way to do this w/.o str conversion?
                cell = str(cell)
            py_columns[col_name].append(cell)
    table = pa.table(py_columns)
    return pc.sort_indices(
        table,
        sort_keys=[
            (col_name, "ascending" if dir_name == "asc" else "descending")
            for col_name, dir_name in zip(py_columns.keys(), col_dirs)
        ],
    )


ArrowWeaveListObjectTypeVar = typing.TypeVar("ArrowWeaveListObjectTypeVar")


def map_output_type(input_types):
    return ArrowWeaveListType(input_types["map_fn"].output_type)


def awl_group_by_result_object_type(
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


def recursively_encode_pyarrow_strings_as_dictionaries(array: pa.Array) -> pa.Array:
    if pa.types.is_struct(array.type):
        return pa.StructArray.from_arrays(
            [
                recursively_encode_pyarrow_strings_as_dictionaries(
                    array.field(field.name)
                )
                for field in array.type
            ],
            [field.name for field in array.type],
        )
    elif pa.types.is_list(array.type):
        return pa.ListArray.from_arrays(
            array.offsets,
            recursively_encode_pyarrow_strings_as_dictionaries(array.flatten()),
        )
    elif array.type == pa.string():
        return pc.dictionary_encode(array)
    else:
        return array


def awl_group_by_result_type(
    object_type: types.Type, key_type: types.Type
) -> "ArrowWeaveListType":
    return ArrowWeaveListType(awl_group_by_result_object_type(object_type, key_type))


def _sort_structs(array: pa.Array) -> pa.Array:
    if isinstance(array, pa.ChunkedArray):
        return pa.chunked_array(
            [_sort_structs(chunk) for chunk in array.chunks], array.type
        )
    if pa.types.is_struct(array.type):
        field_names = sorted([f.name for f in array.type])
        sub_fields = [_sort_structs(array.field(f)) for f in field_names]
        return pa.StructArray.from_arrays(sub_fields, field_names)
    elif pa.types.is_list(array.type):
        return pa.ListArray.from_arrays(
            array.offsets,
            _sort_structs(array.flatten()),
        )
    return array


# When concatenating arrays, the structs need to have the same key order. This
# method attempts reshape StructArrays to have the same nested key order in
# order to safely concat them. If this is not done, arrow will throw an error
# like: `arrays to be concatenated must be identically typed, but ...`
def safe_pa_concat_arrays(arrays):
    if len(arrays) < 2:
        return pa.concat_arrays(arrays)
    t = arrays[0].type
    if all(a.type == t for a in arrays):
        return pa.concat_arrays(arrays)
    if isinstance(t, pa.StructType):
        return pa.concat_arrays([_sort_structs(array) for array in arrays])
    return pa.concat_arrays(arrays)


@weave_class(weave_type=ArrowWeaveListType)
class ArrowWeaveList(typing.Generic[ArrowWeaveListObjectTypeVar]):
    _arrow_data: typing.Union[pa.Table, pa.ChunkedArray, pa.Array]
    object_type: types.Type

    # TODO: Refactor to disable None artifact? (Only used in tests)
    def __init__(
        self,
        _arrow_data,
        object_type=None,
        artifact: typing.Optional[artifact_base.Artifact] = None,
    ) -> None:
        self._arrow_data = _arrow_data
        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._arrow_data).object_type
        self._artifact = artifact
        self._mapper = mappers_arrow.map_from_arrow(self.object_type, self._artifact)
        # TODO: construct mapper

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
            return pa.ListArray.from_arrays(
                offsets, flattened, mask=pa.compute.is_null(arrow_data)
            )

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

                return pa.UnionArray.from_dense(
                    self._arrow_data.type_codes,
                    self._arrow_data.offsets,
                    tag_stripped_members,
                )

        return arrow_data

    def __array__(self, dtype=None):
        return np.asarray(arrow.safe_array_to_pylist(arrow_as_array(self._arrow_data)))

    def __iter__(self):
        for item in arrow.safe_array_to_pylist(arrow_as_array(self._arrow_data)):
            yield self._mapper.apply(item)

    def __repr__(self):
        return f"<ArrowWeaveList: {self.object_type}>"

    def to_pylist_notags(self):
        return arrow.safe_array_to_pylist(self._arrow_data_asarray_no_tags())

    def to_pylist(self):
        if isinstance(self, graph.Node):
            return []
        return arrow.safe_array_to_pylist(arrow_as_array(self._arrow_data))

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

    @op(
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
        res = _apply_fn_node_with_tag_pushdown(self, map_fn)
        return res

    @op(
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
        if not types.optional(types.union(types.String(), types.Number())).assign_type(
            comp_fn.type.object_type
        ):
            # Protection! Arrow cannot handle executing a sort on non-primitives.
            # We will defer to a slower python implementation in these cases.
            awl_or_list = _apply_fn_node_maybe_awl(pushdown_list_tags(self), comp_fn)
            indicies = _slow_arrow_or_list_ranking(awl_or_list, col_dirs)
        else:
            ranking = _apply_fn_node_with_tag_pushdown(self, comp_fn)
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
        mask = _apply_fn_node_with_tag_pushdown(self, filter_fn)
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
        if isinstance(mapper.result_type(), arrow_util.ArrowTypeWithFieldInfo):
            desired_type_pyarrow_type = mapper.result_type().type
        else:
            desired_type_pyarrow_type = mapper.result_type()

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
                tag_array_type = desired_type_pyarrow_type.field("_tag")
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
                                pa.nulls(
                                    len(self), type=desired_type_pyarrow_type[key].type
                                ),
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
                self._arrow_data.cast(desired_type_pyarrow_type),
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
                    offsets,
                    flattened_converted._arrow_data,
                    type=desired_type_pyarrow_type,
                ),
                desired_type,
                self._artifact,
            )

        elif isinstance(desired_type, types.UnionType) and desired_type.assign_type(
            current_type
        ):

            if isinstance(current_type, types.NoneType):
                # If the current type is None, then we can just return a new
                # array with the desired type - based on the above we already
                # know they are assignable.

                result = ArrowWeaveList(
                    pa.nulls(len(self), type=desired_type_pyarrow_type),
                    desired_type,
                    self._artifact,
                )
            else:

                non_none_desired = types.non_none(desired_type)
                if isinstance(non_none_desired, types.UnionType):
                    non_nullable_types = non_none_desired.members
                else:
                    non_nullable_types = [non_none_desired]

                non_null_current_type = types.non_none(current_type)

                if len(non_nullable_types) > 1:
                    # At this point, the objective is to build M arrays, where M is
                    # the number of members in the desired union type. Each array
                    # corresponds to the nth member of the desired union type, and
                    # will contains all nulls, except values for the index in which
                    # the current array is the corresponding type. This will then be
                    # combined in the end via `UnionArray.from_sparse`.
                    #
                    # The logic is only slightly different when the current type is a union,
                    # so we handle both cases in the same code block.

                    # First, we need to create an array which indicates the type code (type index)
                    # for each value in the current array. In the case that the current array is not
                    # a union, then we can just use the type code of the current type. Else, we need
                    # to map the type codes of the current array to the type codes of the desired array.
                    if not isinstance(non_null_current_type, types.UnionType):
                        # In this case we have single type:
                        type_code = mapper.type_code_of_type(non_null_current_type)
                        type_code_array = pa.repeat(type_code, len(self)).cast(
                            pa.int8()
                        )
                        offsets = pa.array(range(len(self)), type=pa.int32())
                    else:
                        curr_type_code_to_desired_type_code = [
                            mapper.type_code_of_type(t)
                            for t in non_null_current_type.members
                        ]
                        current_type_code_list = self._arrow_data.type.type_codes
                        type_encoding = dict(
                            zip(
                                current_type_code_list,
                                curr_type_code_to_desired_type_code,
                            )
                        )

                        def new_type_code_gen():
                            for code in self._arrow_data.type_codes:
                                yield type_encoding[code.as_py()]

                        type_code_array = pa.array(new_type_code_gen(), type=pa.int8())
                        offsets = self._arrow_data.offsets

                    # Next, we are going to build the M arrays. We will do this by iterating
                    # over the desired types. For each type, we will find the corresponding
                    # type in the current type, and then select the corresponding values from
                    # the current array. If there is no corresponding type, then we will create
                    # an array of nulls.
                    data_arrays: list[pa.Array] = []
                    non_null_current_types = (
                        non_null_current_type.members
                        if isinstance(non_null_current_type, types.UnionType)
                        else [non_null_current_type]
                    )
                    for member in non_nullable_types:
                        for curr_ndx, curr_member in enumerate(non_null_current_types):
                            if member.assign_type(
                                curr_member
                            ) and curr_member.assign_type(member):
                                # Here we have found the corresponding type in the current array.
                                # If the current array is a union, then we need to select the
                                # corresponding field. Else, we can just use the current array.
                                if isinstance(non_null_current_type, types.UnionType):
                                    selection = self._arrow_data.field(curr_ndx)
                                else:
                                    selection = self._arrow_data
                                data_arrays.append(selection)
                                break
                        else:
                            # Here we have not found the corresponding type in the current array.
                            # We will create an array of nulls.
                            member_mapper = mappers_arrow.map_to_arrow(
                                member, self._artifact
                            )
                            data_arrays.append(
                                pa.nulls(len(self), type=member_mapper.result_type())
                            )

                    # Finally, combine the M arrays into a single union array.
                    result = ArrowWeaveList(
                        pa.UnionArray.from_dense(
                            type_code_array,
                            offsets,
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
        if len(self) == 0:
            return other
        if len(other) == 0:
            return self
        arrow_data = [arrow_as_array(awl._arrow_data) for awl in (self, other)]
        if arrow_data[0].type == arrow_data[1].type:
            return ArrowWeaveList(
                safe_pa_concat_arrays(arrow_data), self.object_type, self._artifact
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
                safe_pa_concat_arrays(new_arrow_arrays), new_object_type, self._artifact
            )

    @op(
        input_type={
            "self": ArrowWeaveListType(),
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: awl_group_by_result_type(
            input_types["self"].object_type, input_types["group_by_fn"].output_type
        ),
    )
    def groupby(self, group_by_fn):
        group_table_awl = _apply_fn_node_with_tag_pushdown(self, group_by_fn)
        table = self._arrow_data

        group_table = group_table_awl._arrow_data
        group_table_as_array = arrow.arrow_as_array(group_table)

        # strip tags recursively so we group on values only
        # TODO: even though we are stripping tags for the grouping,
        # the groupkey itself should retain its tags. For now this is not
        # practically a problem, but we may want to revisit this in the future.
        group_table_as_array_awl = ArrowWeaveList(
            group_table_as_array, group_table_awl.object_type, self._artifact
        )
        group_table_as_array_awl_stripped = (
            group_table_as_array_awl._arrow_data_asarray_no_tags()
        )
        stripped_type = types.TypeRegistry.type_of(
            group_table_as_array_awl_stripped
        ).object_type

        group_table_chunked = pa.chunked_array(
            pa.StructArray.from_arrays(
                [
                    group_table_as_array_awl_stripped,
                ],
                names=["group_key"],
            )
        )
        group_table_chunked_unzipped = unzip_struct_array(group_table_chunked)
        group_cols = group_table_chunked_unzipped.column_names

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
            types.TypedDict({"groupKey": stripped_type}),
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


def _apply_fn_node_with_tag_pushdown(
    awl: ArrowWeaveList, fn: graph.OutputNode
) -> ArrowWeaveList:
    tagged_awl = pushdown_list_tags(awl)
    return _apply_fn_node(tagged_awl, fn)


def _apply_fn_node(awl: ArrowWeaveList, fn: graph.OutputNode) -> ArrowWeaveList:
    res = _apply_fn_node_maybe_awl(awl, fn)
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


def _apply_fn_node_maybe_awl(
    awl: ArrowWeaveList, fn: graph.OutputNode
) -> typing.Optional[ArrowWeaveList]:
    vectorized_fn = vectorize(fn)
    index_awl: ArrowWeaveList[int] = ArrowWeaveList(pa.array(np.arange(len(awl))))
    row_type = ArrowWeaveListType(awl.object_type)
    fn_res_node = weave_internal.call_fn(
        vectorized_fn,
        {
            "row": weave_internal.make_const_node(row_type, awl),
            "index": weave_internal.make_const_node(
                ArrowWeaveListType(types.Int()), index_awl
            ),
        },
    )

    return use(fn_res_node)


def pushdown_list_tags(arr: ArrowWeaveList) -> ArrowWeaveList:
    if tag_store.is_tagged(arr):
        tag = tag_store.get_tags(arr)
        tag_type = types.TypeRegistry.type_of(tag)
        tag_no_dictionary = to_arrow([tag])._arrow_data
        tag_maybe_dictionary_encoded = (
            recursively_encode_pyarrow_strings_as_dictionaries(tag_no_dictionary)
        )
        tags = pa.repeat(tag_maybe_dictionary_encoded[0], len(arr))
        return awl_add_arrow_tags(arr, tags, tag_type)
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


def _create_manually_mapped_op(
    op_name: str,
    inputs: typing.Dict[str, graph.Node],
    vectorized_keys: set[str],
):
    if len(vectorized_keys) == 1:
        return _create_manually_mapped_op_singular(
            op_name, inputs, list(vectorized_keys)[0]
        )
    op = registry_mem.memory_registry.get_op(op_name)
    inputs = _vectorized_inputs_as_awl_non_vectorized_as_lists(inputs, vectorized_keys)

    mapped_inputs = {k: v for k, v in inputs.items() if k in vectorized_keys}
    rest_inputs = {k: v for k, v in inputs.items() if k not in vectorized_keys}

    from . import dict

    input_arr = dict.arrow_dict_(**mapped_inputs).to_py()

    map_op = registry_mem.memory_registry.get_op("map")
    return map_op(
        input_arr,
        lambda input_dict: op(
            **{k: input_dict[k] for k in mapped_inputs}, **rest_inputs
        ),
    )


def _create_manually_mapped_op_singular(
    op_name: str,
    inputs: typing.Dict[str, graph.Node],
    vectorized_key: str,
):
    op = registry_mem.memory_registry.get_op(op_name)
    inputs = _vectorized_inputs_as_list(inputs, set([vectorized_key]))

    rest_inputs = {k: v for k, v in inputs.items() if k != vectorized_key}

    input_arr = inputs[vectorized_key]

    map_op = registry_mem.memory_registry.get_op("map")
    return map_op(
        input_arr,
        lambda row: op(**{vectorized_key: row}, **rest_inputs),
    )


def _type_is_assignable_to_awl_list(t: types.Type) -> bool:
    return ArrowWeaveListType().assign_type(t)


def _type_is_assignable_to_py_list_not_awl_list(t: types.Type) -> bool:
    return types.List().assign_type(t) and not _type_is_assignable_to_awl_list(t)


def _ensure_list_like_node_is_awl(node: graph.Node) -> graph.Node:
    """
    Ensures that the node is an ArrowWeaveList by appending a conversion op (or stripping
    off an existing conversion op if possible)
    """
    if _type_is_assignable_to_awl_list(node.type):
        return node
    elif _type_is_assignable_to_py_list_not_awl_list(node.type):
        if (
            isinstance(node, graph.OutputNode)
            and node.from_op.name == "ArrowWeaveList-to_py"
        ):
            return list(node.from_op.inputs.values())[0]
        else:
            return list_to_arrow(node)
    else:
        return node


def _ensure_list_like_node_is_list(node: graph.Node) -> graph.Node:
    """
    Ensures that the node is an list by appending a conversion op (or stripping
    off an existing conversion op if possible)
    """
    if _type_is_assignable_to_py_list_not_awl_list(node.type):
        return node
    elif _type_is_assignable_to_awl_list(node.type):
        if (
            isinstance(node, graph.OutputNode)
            and node.from_op.name == "op-list_to_arrow"
        ):
            return list(node.from_op.inputs.values())[0]
        else:
            return ArrowWeaveList.to_py(node)
    else:
        return node


def _process_vectorized_inputs(
    inputs: dict[str, graph.Node],
    vectorized_keys: set[str],
    on_path: typing.Optional[typing.Callable] = None,
    off_path: typing.Optional[typing.Callable] = None,
) -> dict[str, graph.Node]:
    def identity(x):
        return x

    if on_path is None:
        on_path = identity
    if off_path is None:
        off_path = identity
    return {
        k: (on_path(in_node) if k in vectorized_keys else off_path(in_node))
        for k, in_node in inputs.items()
    }


def _vectorized_inputs_as_list(
    inputs: dict[str, graph.Node], vectorized_keys: set[str]
) -> dict[str, graph.Node]:
    return _process_vectorized_inputs(
        inputs, vectorized_keys, on_path=_ensure_list_like_node_is_list
    )


def _vectorized_inputs_as_awl(
    inputs: dict[str, graph.Node], vectorized_keys: set[str]
) -> dict[str, graph.Node]:
    return _process_vectorized_inputs(
        inputs, vectorized_keys, on_path=_ensure_list_like_node_is_awl
    )


def _vectorized_inputs_as_awl_non_vectorized_as_lists(
    inputs: dict[str, graph.Node], vectorized_keys: set[str]
) -> dict[str, graph.Node]:
    return _process_vectorized_inputs(
        inputs,
        vectorized_keys,
        on_path=_ensure_list_like_node_is_awl,
        off_path=_ensure_list_like_node_is_list,
    )


def _vectorize_lambda_output_node(node: graph.OutputNode, vectorized_keys: set[str]):
    # In a situation where we are trying to vectorize a "lambda"
    # function and the input is a a weave arrow list, then we are ina
    # bit of a pickle. This means we are trying to vectorize applying
    # this lambda to each element of the AWL. For example:
    # awl([[{"a":1, "b": 1}, {"a": 1, "b": 2}], [{"a": 2, "b": 3}, {"a": 2, "b": 4}]]).map(lambda row: row.groupby(lambda row: row["a"]))
    # When we hit the inner groupby, we are in this case. This is not
    # possible to vectorize grouping inside of a map. I think we could
    # figure out how to support nested mapping, but all the other pairs
    # are not possible to vectorize (to my knowledge). Therefore, in
    # these cases, we want to forcibly bail out to the list map which
    # does a `execute_fast.fast_map_fn` on each element of the list.
    return _create_manually_mapped_op_singular(
        node.from_op.name,
        node.from_op.inputs,
        "arr",
    )


def _is_lambda_output_node(node: graph.OutputNode):
    return (
        node.from_op.name.endswith("map")
        or node.from_op.name.endswith("groupby")
        or node.from_op.name.endswith("filter")
        or node.from_op.name.endswith("sort")
    )


def _safe_get_op_for_inputs(
    name: str, inputs: dict[str, graph.Node]
) -> typing.Optional[op_def.OpDef]:
    try:
        return dispatch.get_op_for_inputs(name, {k: v.type for k, v in inputs.items()})
    except errors.WeaveDispatchError:
        return None


def _safe_get_weavified_op(op: op_def.OpDef) -> typing.Optional[graph.Node]:
    if op.weave_fn is None:
        try:
            op.weave_fn = weavify.op_to_weave_fn(op)
        except (
            errors.WeaveInternalError,
            errors.WeavifyError,
            errors.WeaveDispatchError,
            errors.WeaveTypeError,
        ):
            pass
    return op.weave_fn


def _vectorize_list_special_case(node_name, node_inputs, vectorized_keys):
    # Unfortunately, we need to check to see if the types are all the same
    # else arrow cannot make the list.
    possible_inputs = _vectorized_inputs_as_awl_non_vectorized_as_lists(
        node_inputs, vectorized_keys
    )
    running_type = None
    is_valid = True
    for v in possible_inputs.values():
        if isinstance(v.type, ArrowWeaveListType):
            obj_type = v.type.object_type
            if running_type is None:
                running_type = obj_type
            elif not running_type.assign_type(obj_type):
                is_valid = False
                break
    if is_valid:
        # TODO: If the AWL types are not all the same, it will bust here.
        op = registry_mem.memory_registry.get_op("ArrowWeaveList-vectorizedList")
        return op.lazy_call(**possible_inputs)
    else:
        return _create_manually_mapped_op(
            node_name,
            possible_inputs,
            vectorized_keys,
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
            if node.from_op.name == "number-bin":
                bin_fn = weave_internal.use(inputs["bin_fn"])
                in_ = inputs["in_"]
                return weave_internal.call_fn(bin_fn, {"row": in_})  # type: ignore
        return node

    def vectorize_output_node(node: graph.OutputNode, vectorized_keys: set[str]):
        # In this function, we will "vectorize" an output_node. This is a
        # shallow mapper against an output node with var nodes in its ancestry.
        # All VarNodes in the original graph will be converted to a AWL of the
        # same type. See `vectorize_along_wrt_paths` for the outer loop that
        # calls this function and performs this variable replacement.
        #
        # Moreover, we are provided a list of keys for the inputs which are in
        # the "vectorization" path. This is important bookkeeping to understand
        # if a list-like input is to be treated as a single list for each "loop"
        # of the vectorization pass (non vectorized path); or if the list-like input
        # is in the vectorization path, meaning each "loop" of the pass should "iterate"
        # over the elements. For example, consider ArrowWeaveList-vectorizedDict:
        #
        # vectorizedDict({
        #   "a": [1, 2, 3], # vectorized path
        #   "b": [4, 5, 6], # vectorized path
        # }) = [
        #   {"a": 1, "b": 4},
        #   {"a": 2, "b": 5},
        #   {"a": 3, "b": 6},
        # ]
        #
        # vectorizedDict({
        #   "a": [1, 2, 3], # vectorized path
        #   "b": [4, 5, 6], # non-vector path
        # }) = [
        #   {"a": 1, "b": [4,5,6]},
        #   {"a": 2, "b": [4,5,6]},
        #   {"a": 3, "b": [4,5,6]},
        # ]
        #
        #
        # So, the main purpose of this function is to say: given these new inputs,
        # dispatch to the correct op such that the result is properly vectorized.

        node_inputs = node.from_op.inputs
        node_name = node.from_op.name

        # First, we need to handle a a few special cases:
        # 1. If the node is a lambda function, then we know we can't vectorize it
        if _is_lambda_output_node(node):
            # Example: [[1,2,3], [3,4,5]].map(row => row.map(x => x + 1))
            return _vectorize_lambda_output_node(node, vectorized_keys)

        # 2. If the op is `dict` or `list` then we manually hard code the vectorized version
        # since dispatch will choose the non-vectorized version. Note that we transform the inputs
        # appropriately. See comments in header of function
        if node_name == "dict":
            op = registry_mem.memory_registry.get_op("ArrowWeaveList-vectorizedDict")
            return op.lazy_call(
                **_vectorized_inputs_as_awl_non_vectorized_as_lists(
                    node_inputs, vectorized_keys
                )
            )
        if node_name == "list":
            return _vectorize_list_special_case(node_name, node_inputs, vectorized_keys)

        # 3. In the case of `Object-__getattr__`, we need to special case it will only work when the first arg is AWL
        # and the second is a string:
        if node_name == "Object-__getattr__":
            arg_names = list(node_inputs.keys())
            if arg_names[0] in vectorized_keys and arg_names[1] not in vectorized_keys:
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveListObject-__vectorizedGetattr__"
                )
                return op.lazy_call(
                    **{
                        arg_names[0]: _ensure_list_like_node_is_awl(
                            node_inputs[arg_names[0]]
                        ),
                        arg_names[1]: node_inputs[arg_names[1]],
                    }
                )

        # Now, if we have not returned by now, then we can move on to the main logic of this function.

        # Part 1: Attempt to dispatch using the AWL inputs (This would be the most ideal case - pure AWL)
        inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
        maybe_op = _safe_get_op_for_inputs(node_name, inputs_as_awl)
        if maybe_op is not None:
            return maybe_op.lazy_call(*inputs_as_awl.values())

        # Part 2: We still want to use Arrow if possible. Here we are going to attempt to
        # weavify, then vectorize the op implementation.
        node_op = registry_mem.memory_registry.get_op(node_name)
        maybe_weavified_op = _safe_get_weavified_op(node_op)
        if maybe_weavified_op is not None:
            with_respect_to = None  # TODO: only vectorize the vectorization path!
            vectorized = vectorize(
                maybe_weavified_op, with_respect_to, stack_depth=stack_depth + 1
            )
            return weave_internal.call_fn(vectorized, inputs_as_awl)

        # Part 3: Attempt to dispatch using the list-like inputs (this is preferred to the final case)
        inputs_as_list = _vectorized_inputs_as_list(node_inputs, vectorized_keys)
        maybe_op = _safe_get_op_for_inputs(node_name, inputs_as_list)
        if maybe_op is not None:
            return maybe_op.lazy_call(*inputs_as_list.values())

        # Final Fallback: We have no choice anymore. We must bail out completely to mapping
        # over all the vectorized inputs and calling the function directly.
        # If we hit this, then it means our vectorization has
        # created inputs which have no matching op. For example,
        # if we are doing a pick operation and the key is a
        # vectorized VarNode. This happens when picking a run
        # color using a vectorized list of runs for a table
        # (since pick(dict, list<string>) is not implemented).
        # This can happen for other ops like `add` and `mul` as
        # well (imagine `row => 1 + row`)
        #
        # In order to safely handle this case, we need to simply map
        # the original op over all the vectorized inputs.
        res = _create_manually_mapped_op(
            node_name,
            node_inputs,
            vectorized_keys,
        )
        message = f"Encountered non-dispatchable op ({node_name}) during vectorization."
        message += f"This is likely due to vectorization path of the function not leading to the"
        message += f"first parameter. Bailing out to manual mapping"
        logging.warning(message)
        return res

    # Vectorize is "with respect to" (wrt) specific variable nodes in the graph.
    # vectorize_along_wrt_paths keeps track of nodes that have already
    # been vectorized, ie nodes that have a wrt variable in their ancestry.
    # We don't try to vectorize paths for which that is not the case.
    already_vectorized_nodes: set[graph.Node] = set()

    def vectorize_along_wrt_paths(node: graph.Node):
        if isinstance(node, graph.OutputNode):
            vectorized_keys = set()
            for input_key, input_node in node.from_op.inputs.items():
                if input_node in already_vectorized_nodes:
                    vectorized_keys.add(input_key)
            if len(vectorized_keys) == 0:
                # not along vectorize path
                return node
            new_node = vectorize_output_node(node, vectorized_keys)
            already_vectorized_nodes.add(new_node)
            return new_node
        elif isinstance(node, graph.VarNode):
            # Vectorize variable
            if with_respect_to is None or any(
                node is wrt_node for wrt_node in with_respect_to
            ):
                new_node = graph.VarNode(ArrowWeaveListType(node.type), node.name)
                already_vectorized_nodes.add(new_node)
                return new_node
            # not along vectorize path
            return node
        elif isinstance(node, graph.ConstNode):
            # not along vectorize path
            return node
        else:
            raise errors.WeaveInternalError("Unexpected node: %s" % node)

    weave_fn = graph.map_nodes_top_level(
        [weave_fn], ensure_object_constructors_created
    )[0]
    weave_fn = graph.map_nodes_top_level([weave_fn], expand_nodes)[0]
    return graph.map_nodes_top_level([weave_fn], vectorize_along_wrt_paths)[0]


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

    def none_unboxer(iterator: typing.Iterable):
        for obj in iterator:
            if isinstance(obj, box.BoxedNone):
                # get rid of box
                yield None
            else:
                yield obj

    if isinstance(mapper.type, types.UnionType) and mapper.type.is_simple_nullable():
        nonnull_mapper = [
            m for m in mapper._member_mappers if m.type != types.NoneType()
        ][0]

        return recursively_build_pyarrow_array(
            list(none_unboxer(py_objs)),
            pyarrow_type,
            nonnull_mapper,
            py_objs_already_mapped,
        )
    elif pa.types.is_null(pyarrow_type):
        return pa.array(
            none_unboxer(py_objs),
            type=pyarrow_type,
        )
    elif pa.types.is_struct(pyarrow_type):
        keys: list[str] = []
        # keeps track of null values so that we can null entries at the struct level
        mask: list[bool] = []

        assert isinstance(
            mapper,
            (
                mappers_arrow.TypedDictToArrowStruct,
                mappers_arrow.TaggedValueToArrowStruct,
                mappers_arrow.ObjectToArrowStruct,
            ),
        )

        # handle empty struct case - the case where the struct has no fields
        if len(pyarrow_type) == 0:
            return pa.array(py_objs, type=pyarrow_type)

        for i, field in enumerate(pyarrow_type):
            data: list[typing.Any] = []
            if isinstance(
                mapper,
                mappers_arrow.TypedDictToArrowStruct,
            ):

                for py_obj in py_objs:
                    if py_obj is None:
                        data.append(None)
                    else:
                        data.append(py_obj.get(field.name, None))
                    if i == 0:
                        mask.append(py_obj is None)

                array = recursively_build_pyarrow_array(
                    data,
                    field.type,
                    mapper._property_serializers[field.name],
                    py_objs_already_mapped,
                )
            if isinstance(
                mapper,
                mappers_arrow.ObjectToArrowStruct,
            ):
                for py_obj in py_objs:
                    if py_obj is None:
                        data.append(None)
                    elif py_objs_already_mapped:
                        data.append(py_obj.get(field.name, None))
                    else:
                        data.append(getattr(py_obj, field.name, None))
                    if i == 0:
                        mask.append(py_obj is None)

                array = recursively_build_pyarrow_array(
                    data,
                    field.type,
                    mapper._property_serializers[field.name],
                    py_objs_already_mapped,
                )

            elif isinstance(mapper, mappers_arrow.TaggedValueToArrowStruct):
                if field.name == "_tag":
                    for py_obj in py_objs:
                        if py_obj is None:
                            data.append(None)
                        else:
                            data.append(tag_store.get_tags(py_obj))
                        if i == 0:
                            mask.append(py_obj is None)

                    array = recursively_build_pyarrow_array(
                        data,
                        field.type,
                        mapper._tag_serializer,
                        py_objs_already_mapped,
                    )
                else:
                    for py_obj in py_objs:
                        if py_obj is None:
                            data.append(None)
                        else:
                            data.append(box.unbox(py_obj))
                        if i == 0:
                            mask.append(py_obj is None)

                    array = recursively_build_pyarrow_array(
                        data,
                        field.type,
                        mapper._value_serializer,
                        py_objs_already_mapped,
                    )

            arrays.append(array)
            keys.append(field.name)
        return pa.StructArray.from_arrays(
            arrays, keys, mask=pa.array(mask, type=pa.bool_())
        )
    elif pa.types.is_union(pyarrow_type):
        assert isinstance(mapper, mappers_arrow.UnionToArrowUnion)
        type_codes: list[int] = [mapper.type_code_of_obj(o) for o in py_objs]
        offsets: list[int] = []
        py_data: list[list] = []
        for _ in range(len(pyarrow_type)):
            py_data.append([])

        for row_index, type_code in enumerate(type_codes):
            offsets.append(len(py_data[type_code]))
            py_data[type_code].append(py_objs[row_index])

        for i, raw_py_data in enumerate(py_data):
            array = recursively_build_pyarrow_array(
                raw_py_data,
                pyarrow_type.field(i).type,
                mapper.mapper_of_type_code(i),
                py_objs_already_mapped,
            )
            arrays.append(array)

        return pa.UnionArray.from_dense(
            pa.array(type_codes, type=pa.int8()),
            pa.array(offsets, type=pa.int32()),
            arrays,
        )
    if py_objs_already_mapped:
        return pa.array(py_objs, pyarrow_type)
    return pa.array(
        [mapper.apply(o) if o is not None else None for o in py_objs], pyarrow_type
    )


# This will be a faster version fo to_arrow (below). Its
# used in op file-table, to convert from a wandb Table to Weave
# (that code is very experimental and not totally working yet)
def to_arrow_from_list_and_artifact(
    obj: typing.Any, object_type: types.Type, artifact: artifact_base.Artifact
) -> ArrowWeaveList:
    # Get what the parquet type will be.
    merged_object_type = recursively_merge_union_types_if_they_are_unions_of_structs(
        object_type
    )
    mapper = mappers_arrow.map_to_arrow(merged_object_type, artifact)
    pyarrow_type = mapper.result_type()

    arrow_obj = recursively_build_pyarrow_array(
        obj, pyarrow_type, mapper, py_objs_already_mapped=True
    )
    return ArrowWeaveList(arrow_obj, merged_object_type, artifact)


def to_arrow(obj, wb_type=None):
    if isinstance(obj, ArrowWeaveList):
        return obj
    if wb_type is None:
        wb_type = types.TypeRegistry.type_of(obj)
    artifact = artifact_mem.MemArtifact()
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

        arrow_obj = recursively_build_pyarrow_array(obj, pyarrow_type, mapper)
        weave_obj = ArrowWeaveList(arrow_obj, merged_object_type, artifact)

        # Save the weave object to the artifact
        # ref = storage.save(weave_obj, artifact=artifact)
        if outer_tags is not None:
            tag_store.add_tags(weave_obj, outer_tags)

        return weave_obj

    raise errors.WeaveInternalError("to_arrow not implemented for: %s" % obj)


@op(
    input_type={
        "arr": types.List(),
    },
    output_type=lambda input_types: ArrowWeaveListType(input_types["arr"].object_type),
)
def list_to_arrow(arr):
    return to_arrow(arr)


def direct_add_arrow_tags(
    data: typing.Union[pa.Table, pa.Array], arrow_tags: pa.StructArray
):
    arrow_tags = recursively_encode_pyarrow_strings_as_dictionaries(arrow_tags)
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
    if isinstance(data, pa.Table):
        if current_tags is not None:
            new_value = data["_value"]
        else:
            new_value = pa.StructArray.from_arrays(
                # TODO: we shouldn't need to combine chunks, we can produce this in the
                # original chunked form for zero copy
                [c.combine_chunks() for c in data.columns],
                names=data.column_names,
            )
    elif isinstance(data, pa.StructArray):
        if current_tags is not None:
            new_value = data.field("_value")
        else:
            new_value = data
    else:
        # Else its an arrow array
        new_value = data
    return pa.StructArray.from_arrays([tag_array, new_value], ["_tag", "_value"])


def awl_add_arrow_tags(
    l: ArrowWeaveList, arrow_tags: pa.StructArray, tag_type: types.Type
):
    data = l._arrow_data
    new_value = direct_add_arrow_tags(data, arrow_tags)
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
    artifact: typing.Optional[artifact_base.Artifact]


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
    concatted = safe_pa_concat_arrays(res.arrays)
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


def _join_all_output_type(input_types):
    arr_prop_types = input_types["arrs"].object_type.object_type.property_types
    prop_types = {}
    for k in arr_prop_types.keys():
        prop_types[k] = types.List(types.optional(arr_prop_types[k]))
    inner_type = types.TypedDict(prop_types)
    tag_type = types.TypedDict({"joinObj": input_types["joinFn"].output_type})
    tagged_type = tagged_value_type.TaggedValueType(tag_type, inner_type)
    return ArrowWeaveListType(tagged_type)


def _filter_none(arrs: list[typing.Any]) -> list[typing.Any]:
    return [a for a in arrs if a != None]


def _awl_struct_array_to_table(awl: ArrowWeaveList) -> pa.Table:
    assert isinstance(awl.object_type, types.TypedDict)
    columns = list(awl.object_type.property_types.keys())
    arrays = [awl._arrow_data.field(k) for k in columns]
    return pa.Table.from_arrays(arrays, columns)


@op(
    name="ArrowWeaveList-joinAll",
    input_type={
        "arrs": types.List(types.optional(ArrowWeaveListType(types.TypedDict({})))),
        "joinFn": lambda input_types: types.Function(
            {"row": input_types["arrs"].object_type.object_type}, types.Any()
        ),
    },
    output_type=_join_all_output_type,
)
def join_all(arrs, joinFn, outer: bool):
    # This is a pretty complicated op. See list.ts for the original implementation

    # First, filter out Nones
    arrs = _filter_none(arrs)

    # If nothing remains, simply return.
    if len(arrs) == 0:
        return ArrowWeaveList(pa.array([]), types.TypedDict({}))

    # Execute the joinFn on each of the arrays
    arrs_keys = [
        arrow_as_array(_apply_fn_node_with_tag_pushdown(arr, joinFn)._arrow_data)
        for arr in arrs
    ]

    # Get the union of all the keys of all the elements
    arr_keys = []
    all_element_keys: set[str] = set([])
    for arr in arrs:
        keys = set(arr.object_type.property_types.keys())
        arr_keys.append(keys)
        all_element_keys = all_element_keys.union(keys)
    raw_key_to_safe_key = {key: f"c_{ndx}" for ndx, key in enumerate(all_element_keys)}
    safe_key_to_raw_key = {v: k for k, v in raw_key_to_safe_key.items()}
    safe_element_keys = list(raw_key_to_safe_key.values())
    arrs_as_tables = [_awl_struct_array_to_table(arr) for arr in arrs]
    keyed_tables = []
    join_key_col_name = "__joinobj__"
    with duckdb_con() as con:
        for i, (table, arrs_keys) in enumerate(zip(arrs_as_tables, arrs_keys)):
            keyed_table = (
                table.add_column(0, join_key_col_name, arrs_keys)
                .filter(pc.invert(pc.is_null(pc.field(join_key_col_name))))
                .rename_columns(
                    [join_key_col_name]
                    + [
                        raw_key_to_safe_key[lookup_name]
                        for lookup_name in table.column_names
                    ]
                )
            )
            keyed_tables.append(keyed_table)
            con.register(f"t{i}", keyed_table)

        join_type = "full outer" if outer else "inner"

        query = "SELECT COALESCE(%s) as %s" % (
            ", ".join(f"t{i}.{join_key_col_name}" for i in range(len(keyed_tables))),
            join_key_col_name,
        )
        for k in safe_element_keys:
            raw_key = safe_key_to_raw_key[k]
            query += ", list_value(%s) as %s" % (
                ", ".join(
                    f"t{i}.{k}"
                    for i in range(len(keyed_tables))
                    if raw_key in arr_keys[i]
                ),
                k,
            )
        query += "\nFROM t0"
        for t_ndx in range(1, len(keyed_tables)):
            query += f" {join_type} join t{t_ndx} ON t0.{join_key_col_name} = t{t_ndx}.{join_key_col_name}"

        res = con.execute(query)

        final_table = res.arrow()
        join_obj = final_table.column(join_key_col_name).combine_chunks()
        final_table = final_table.drop([join_key_col_name]).rename_columns(
            all_element_keys
        )

        untagged_result: ArrowWeaveList = ArrowWeaveList(
            final_table,
            None,
            arrs[0]._artifact,
        )

        return awl_add_arrow_tags(
            untagged_result,
            pa.StructArray.from_arrays([join_obj], names=["joinObj"]),
            types.TypedDict({"joinObj": joinFn.type}),
        )


def _join_2_output_type(input_types):
    return ArrowWeaveListType(base_list._join_2_output_row_type(input_types))


@op(
    name="ArrowWeaveList-join",
    input_type={
        "arr1": ArrowWeaveListType(types.TypedDict({})),
        "arr2": ArrowWeaveListType(types.TypedDict({})),
        "joinFn1": lambda input_types: types.Function(
            {"row": input_types["arr1"].object_type}, types.Any()
        ),
        "joinFn2": lambda input_types: types.Function(
            {"row": input_types["arr2"].object_type}, types.Any()
        ),
        "alias1": types.String(),
        "alias2": types.String(),
        "leftOuter": types.Boolean(),
        "rightOuter": types.Boolean(),
    },
    output_type=_join_2_output_type,
)
def join_2(arr1, arr2, joinFn1, joinFn2, alias1, alias2, leftOuter, rightOuter):
    # This is a pretty complicated op. See list.ts for the original implementation

    table1 = _awl_struct_array_to_table(arr1)
    table2 = _awl_struct_array_to_table(arr2)

    # Execute the joinFn on each of the arrays
    table1_join_keys = arrow_as_array(
        _apply_fn_node_with_tag_pushdown(arr1, joinFn1)._arrow_data
    )
    table2_join_keys = arrow_as_array(
        _apply_fn_node_with_tag_pushdown(arr2, joinFn2)._arrow_data
    )
    join_obj_type = types.optional(types.union(joinFn1.type, joinFn2.type))

    table1_columns_names = arr1.object_type.property_types.keys()
    table2_columns_names = arr2.object_type.property_types.keys()

    table1_safe_column_names = [f"c_{ndx}" for ndx in range(len(table1_columns_names))]
    table2_safe_column_names = [f"c_{ndx}" for ndx in range(len(table2_columns_names))]

    table1_safe_alias = "a_1"
    table2_safe_alias = "a_2"

    join_key_col_name = "__joinobj__"

    with duckdb_con() as con:

        def create_keyed_table(table_name, table, keys, safe_column_names):
            keyed_table = (
                table.add_column(0, join_key_col_name, keys)
                .filter(pc.invert(pc.is_null(pc.field(join_key_col_name))))
                .rename_columns([join_key_col_name] + safe_column_names)
            )
            con.register(table_name, keyed_table)
            return keyed_table

        create_keyed_table("t1", table1, table1_join_keys, table1_safe_column_names)
        create_keyed_table("t2", table2, table2_join_keys, table2_safe_column_names)

        if leftOuter and rightOuter:
            join_type = "full outer"
        elif leftOuter:
            join_type = "left outer"
        elif rightOuter:
            join_type = "right outer"
        else:
            join_type = "inner"

        query = f"""
        SELECT 
            COALESCE(t1.{join_key_col_name}, t2.{join_key_col_name}) as {join_key_col_name},
            CASE WHEN t1.{join_key_col_name} IS NULL THEN NULL ELSE
                struct_pack({
                    ", ".join(f'{col} := t1.{col}' for col in table1_safe_column_names)
                })
            END as {table1_safe_alias},
            CASE WHEN t2.{join_key_col_name} IS NULL THEN NULL ELSE
                struct_pack({
                    ", ".join(f'{col} := t2.{col}' for col in table2_safe_column_names)
                })
            END as {table2_safe_alias},
        FROM t1 {join_type} JOIN t2 ON t1.{join_key_col_name} = t2.{join_key_col_name}
        """

        res = con.execute(query)

        duck_table = res.arrow()
    join_obj = duck_table.column(join_key_col_name).combine_chunks()
    duck_table = duck_table.drop([join_key_col_name])
    alias_1_res = duck_table.column(table1_safe_alias).combine_chunks()
    alias_1_renamed = pa.StructArray.from_arrays(
        [alias_1_res.field(col_name) for col_name in table1_safe_column_names],
        table1_columns_names,
        mask=alias_1_res.is_null(),
    )
    alias_2_res = duck_table.column(table2_safe_alias).combine_chunks()
    alias_2_renamed = pa.StructArray.from_arrays(
        [alias_2_res.field(col_name) for col_name in table2_safe_column_names],
        table2_columns_names,
        mask=alias_2_res.is_null(),
    )
    final_table = pa.StructArray.from_arrays(
        [alias_1_renamed, alias_2_renamed],
        [alias1, alias2],
    )
    untagged_result: ArrowWeaveList = ArrowWeaveList(
        final_table,
        None,
        arr1._artifact,
    )

    res = awl_add_arrow_tags(
        untagged_result,
        pa.StructArray.from_arrays([join_obj], names=["joinObj"]),
        types.TypedDict({"joinObj": join_obj_type}),
    )
    return res


def vectorized_arrow_pick_output_type(input_types):
    inner_type = types.union(*list(input_types["self"].property_types.values()))
    if isinstance(input_types["key"], ArrowWeaveListType):
        return ArrowWeaveListType(inner_type)
    else:
        return types.List(inner_type)


# Combining both list and arrow into the same op since dispatch operates on the
# first input, and the difference would only be in the second input
@op(
    name="_vectorized_list_like-pick",
    input_type={
        "self": types.TypedDict({}),
        "key": types.union(
            ArrowWeaveListType(types.String()), types.List(types.String())
        ),
    },
    output_type=vectorized_arrow_pick_output_type,
)
def vectorized_arrow_pick(self, key):
    if isinstance(key, list):
        return [self.get(k, None) for k in key]
    de = arrow_as_array(key._arrow_data_asarray_no_tags()).dictionary_encode()
    new_dictionary = pa.array(
        [self.get(key, None) for key in de.dictionary.to_pylist()]
    )
    new_indices = de.indices
    new_array = pa.DictionaryArray.from_arrays(new_indices, new_dictionary)
    result = new_array.dictionary_decode()
    return ArrowWeaveList(
        result,
    )


# # Putting this here instead of in number b/c it is just a map function
# bin_type = types.TypedDict({"start": types.Number(), "stop": types.Number()})


# @op(
#     name="ArrowWeaveListNumber-bin",
#     input_type={
#         "val": ArrowWeaveListType(types.optional(types.Number())),
#         "binFn": types.Function(
#             {"row": types.Number()},
#             types.TypedDict({"start": types.Number(), "stop": types.Number()}),
#         ),
#     },
#     output_type=ArrowWeaveListType(types.optional(bin_type)),
# )
# def number_bin(val, binFn):
#     tagged_awl = pushdown_list_tags(val)
#     res = _apply_fn_node(tagged_awl, binFn)
#     return res
