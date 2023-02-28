import typing
import dataclasses
import numpy as np
import pyarrow as pa

from ..ops_domain import wbmedia
from .. import ref_base
from .. import weave_types as types
from .. import box
from .. import errors
from .. import mappers_arrow
from .. import mappers_python_def
from ..language_features.tagging import (
    tagged_value_type,
    tagged_value_type_helpers,
)
from .. import arrow_util
from .. import artifact_base
from .. import node_ref
from ..language_features.tagging import tag_store

from .arrow import arrow_as_array, ArrowWeaveListType, offsets_starting_at_zero
from . import arrow


def reverse_dict(d: dict) -> dict:
    return dict(reversed(d.items()))


def concrete_to_tagstore(val: typing.Any) -> typing.Any:
    if isinstance(val, dict):
        if "_tag" in val and "_value" in val:
            v = box.box(concrete_to_tagstore(val["_value"]))
            tag_store.add_tags(v, concrete_to_tagstore(val["_tag"]))
            return v
        return {k: concrete_to_tagstore(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [concrete_to_tagstore(v) for v in val]
    elif dataclasses.is_dataclass(val):
        params = {
            f.name: concrete_to_tagstore(getattr(val, f.name))
            for f in dataclasses.fields(val)
        }
        return val.__class__(**params)
    return val


ArrowWeaveListObjectTypeVar = typing.TypeVar("ArrowWeaveListObjectTypeVar")


def _sort_structs(array: pa.Array) -> pa.Array:
    if isinstance(array, pa.ChunkedArray):
        return pa.chunked_array(
            [_sort_structs(chunk) for chunk in array.chunks], array.type
        )
    if pa.types.is_struct(array.type):
        if array.type.num_fields == 0:
            return array
        field_names = sorted([f.name for f in array.type])
        sub_fields = [_sort_structs(array.field(f)) for f in field_names]
        return pa.StructArray.from_arrays(sub_fields, field_names)
    elif pa.types.is_list(array.type):
        return pa.ListArray.from_arrays(
            offsets_starting_at_zero(array),
            _sort_structs(array.flatten()),
            mask=pa.compute.is_null(array),
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


@dataclasses.dataclass(frozen=True)
class PathItemOuterList:
    # Denotes this is the outermost list
    pass


@dataclasses.dataclass(frozen=True)
class PathItemStructField:
    key: str


@dataclasses.dataclass(frozen=True)
class PathItemObjectField:
    attr: str


@dataclasses.dataclass(frozen=True)
class PathItemList:
    pass


@dataclasses.dataclass(frozen=True)
class PathItemTaggedValueTag:
    pass


@dataclasses.dataclass(frozen=True)
class PathItemTaggedValueValue:
    pass


@dataclasses.dataclass(frozen=True)
class PathItemUnionEntry:
    type_code: int


PathItemType = typing.Union[
    PathItemOuterList,
    PathItemStructField,
    PathItemObjectField,
    PathItemList,
    PathItemTaggedValueTag,
    PathItemTaggedValueValue,
    PathItemUnionEntry,
]

PathType = tuple[PathItemType, ...]


def set_path(
    v: typing.Any,
    arrow_data: pa.Array,
    path: PathType,
    value_fn: typing.Callable[[typing.Any, int], typing.Any],
    offset: int = 0,
    arrow_offset: int = 0,
):
    arrow_data = arrow.arrow_as_array(arrow_data)
    last_settable_index = len(path) - 1
    final_union_path_el: typing.Optional[PathItemUnionEntry] = None
    if isinstance(path[last_settable_index], PathItemUnionEntry):
        last_settable_index -= 1
        final_union_path_el = path[-1]  # type: ignore
    if isinstance(path[last_settable_index], PathItemUnionEntry):
        raise errors.WeaveInternalError("path ended with two unions, invalid")
    # Helper function for converting arrow to python. Set the value at a path
    # within the value v, using value_fn to get the new value.
    # Path must be of length 1 or greater. Caller needs to handle the case
    # where we want to set v itself (path is of length 0).
    for i, el in enumerate(path[:last_settable_index]):
        if v is None:
            return
        if isinstance(el, PathItemStructField):
            v = v[el.key]
            arrow_data = arrow_data.field(el.key)
        elif isinstance(el, PathItemObjectField):
            v = getattr(v, el.attr)
            arrow_data = arrow_data.field(el.attr)
        elif el == PathItemTaggedValueTag():
            # breakpoint()
            try:
                v = v["_tag"]
            except (TypeError, KeyError):
                v = v.tag
            arrow_data = arrow_data.field("_tag")
        elif el == PathItemTaggedValueValue():
            try:
                v = v["_value"]
            except (TypeError, KeyError):
                v = v.value
            arrow_data = arrow_data.field("_value")
        elif el == PathItemOuterList():
            for j, vi in enumerate(v):
                set_path(
                    vi,
                    arrow_data,
                    path[i + 1 :],
                    value_fn,
                    offset + j,
                    arrow_offset + j,
                )
            return
        elif el == PathItemList():
            # its a list
            for j, vi in enumerate(v):
                set_path(
                    vi,
                    arrow_data.values,
                    path[i + 1 :],
                    value_fn,
                    offset + j,
                    arrow_offset + j,
                )
            return
        elif isinstance(el, PathItemUnionEntry):
            if el.type_code != arrow_data.type_codes[arrow_offset].as_py():
                return
            arrow_data = arrow_data.field(el.type_code)
            arrow_offset = 0
        else:
            raise ValueError(f"Unexpected path element: {el}")
    if v is None:
        return

    leaf = path[last_settable_index]

    if isinstance(leaf, PathItemStructField):
        if final_union_path_el:
            arrow_data = arrow_data.field(leaf.key)
            if (
                final_union_path_el.type_code
                != arrow_data.type_codes[arrow_offset].as_py()
            ):
                return
        v[leaf.key] = value_fn(v[leaf.key], offset)
    elif isinstance(leaf, PathItemObjectField):
        if final_union_path_el:
            arrow_data = arrow_data.field(leaf.attr)
            if (
                final_union_path_el.type_code
                != arrow_data.type_codes[arrow_offset].as_py()
            ):
                return
        setattr(v, leaf.attr, value_fn(getattr(v, leaf.attr), offset))
    elif leaf == PathItemTaggedValueTag():
        if final_union_path_el:
            arrow_data = arrow_data.field("_tag")
            if (
                final_union_path_el.type_code
                != arrow_data.type_codes[arrow_offset].as_py()
            ):
                return
        try:
            v["_tag"] = value_fn(v["_tag"], offset)
        except (KeyError, TypeError):
            v.tag = value_fn(v.tag, offset)
    elif leaf == PathItemTaggedValueValue():
        if final_union_path_el:
            arrow_data = arrow_data.field("_value")
            if (
                final_union_path_el.type_code
                != arrow_data.type_codes[arrow_offset].as_py()
            ):
                return
        try:
            v["_value"] = value_fn(v["_value"], offset)
        except (KeyError, TypeError):
            print("V", v)
            v.value = value_fn(v.value, offset)
    elif leaf == PathItemList():
        if final_union_path_el:
            arrow_data = arrow_data.values
            for j, vi in enumerate(v):
                if (
                    final_union_path_el.type_code
                    != arrow_data.type_codes[arrow_offset + j].as_py()
                ):
                    continue
                v[j] = value_fn(vi, offset + j)
        else:
            for j, vi in enumerate(v):
                v[j] = value_fn(vi, offset + j)
    elif leaf == PathItemOuterList():
        if final_union_path_el:
            for j, vi in enumerate(v):
                if (
                    final_union_path_el.type_code
                    != arrow_data.type_codes[arrow_offset + j].as_py()
                ):
                    continue
                v[j] = value_fn(vi, offset + j)
        else:
            for j, vi in enumerate(v):
                v[j] = value_fn(vi, offset + j)
    else:
        raise ValueError(f"Unexpected path element: {leaf}")


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

    def map_column(
        self,
        fn: typing.Callable[
            ["ArrowWeaveList", PathType], typing.Optional["ArrowWeaveList"]
        ],
    ) -> "ArrowWeaveList":
        return self._map_column(fn, ())

    def _map_column(
        self,
        fn: typing.Callable[
            ["ArrowWeaveList", PathType], typing.Optional["ArrowWeaveList"]
        ],
        path: PathType,
    ) -> "ArrowWeaveList":
        with_mapped_children = self
        if isinstance(self._arrow_data, pa.NullArray):
            # If we are a null array, then there is nothing to map
            return self
        if isinstance(self.object_type, types.Const):
            with_mapped_children = ArrowWeaveList(
                self._arrow_data, self.object_type.val_type, self._artifact
            )._map_column(fn, path)
        elif isinstance(self.object_type, types.TypedDict):
            arr = arrow.arrow_as_array(self._arrow_data)
            properties: dict[str, ArrowWeaveList] = {
                k: ArrowWeaveList(arr.field(k), v, self._artifact)._map_column(
                    fn, path + (PathItemStructField(k),)
                )
                for k, v in self.object_type.property_types.items()
            }
            if not properties:
                result_arr = arr
            else:
                result_arr = pa.StructArray.from_arrays(
                    [v._arrow_data for v in properties.values()],
                    list(properties.keys()),
                    mask=pa.compute.is_null(arr),
                )

            with_mapped_children = ArrowWeaveList(
                result_arr,
                types.TypedDict({k: v.object_type for k, v in properties.items()}),
                self._artifact,
            )
        elif isinstance(self.object_type, types.ObjectType):
            arr = arrow.arrow_as_array(self._arrow_data)
            attrs: dict[str, ArrowWeaveList] = {
                k: ArrowWeaveList(arr.field(k), v, self._artifact)._map_column(
                    fn, path + (PathItemObjectField(k),)
                )
                for k, v in self.object_type.property_types().items()
            }
            with_mapped_children = ArrowWeaveList(
                pa.StructArray.from_arrays(
                    [v._arrow_data for v in attrs.values()],
                    list(attrs.keys()),
                    mask=pa.compute.is_null(arr),
                ),
                self.object_type,
                # Can't do this because The W&B Image types are non-standard :(
                # self.object_type.__class__(
                #     **{k: attrs[k].object_type for k in self.object_type.type_attrs()}
                # ),
                self._artifact,
            )
        elif isinstance(self.object_type, types.List):
            arr = arrow.arrow_as_array(self._arrow_data)
            items: ArrowWeaveList = ArrowWeaveList(
                arr.flatten(), self.object_type.object_type, self._artifact
            )._map_column(fn, path + (PathItemList(),))
            with_mapped_children = ArrowWeaveList(
                pa.ListArray.from_arrays(
                    offsets_starting_at_zero(self._arrow_data),
                    items._arrow_data,
                    mask=pa.compute.is_null(arr),
                ),
                types.List(items.object_type),
                self._artifact,
            )
        elif isinstance(self.object_type, tagged_value_type.TaggedValueType):
            arr = arrow.arrow_as_array(self._arrow_data)
            tag: ArrowWeaveList = ArrowWeaveList(
                self._arrow_data.field("_tag"), self.object_type.tag, self._artifact
            )._map_column(fn, path + (PathItemTaggedValueTag(),))
            if not isinstance(tag.object_type, types.TypedDict):
                raise errors.WeaveInternalError("Tag must be a TypedDict")
            value: ArrowWeaveList = ArrowWeaveList(
                self._arrow_data.field("_value"), self.object_type.value, self._artifact
            )._map_column(fn, path + (PathItemTaggedValueValue(),))
            with_mapped_children = ArrowWeaveList(
                pa.StructArray.from_arrays(
                    [tag._arrow_data, value._arrow_data],
                    ["_tag", "_value"],
                    mask=pa.compute.is_null(arr),
                ),
                tagged_value_type.TaggedValueType(tag.object_type, value.object_type),
                self._artifact,
            )
        elif isinstance(self.object_type, types.UnionType):
            non_none_members = [
                m for m in self.object_type.members if not isinstance(m, types.NoneType)
            ]
            nullable = len(non_none_members) < len(self.object_type.members)
            if len(non_none_members) == 1:
                # simple nullable case
                non_none_member = ArrowWeaveList(
                    self._arrow_data,
                    non_none_members[0],
                    self._artifact,
                )._map_column(fn, path)
                with_mapped_children = ArrowWeaveList(
                    non_none_member._arrow_data,
                    types.optional(non_none_member.object_type),
                    self._artifact,
                )
            elif len(non_none_members) > 1:
                arr = arrow.arrow_as_array(self._arrow_data)
                members: list[ArrowWeaveList] = [
                    ArrowWeaveList(
                        arr.field(i), member_type, self._artifact
                    )._map_column(fn, path + (PathItemUnionEntry(i),))
                    for i, member_type in enumerate(non_none_members)
                ]
                new_type_members = [m.object_type for m in members]
                if nullable:
                    new_type_members.append(types.NoneType())
                with_mapped_children = ArrowWeaveList(
                    pa.UnionArray.from_dense(
                        self._arrow_data.type_codes,
                        self._arrow_data.offsets,
                        [m._arrow_data for m in members],
                    ),
                    types.UnionType(*new_type_members),
                    self._artifact,
                )
            else:
                raise errors.WeaveInternalError(
                    "Union must have at least one non-none member"
                )

        mapped = fn(with_mapped_children, path)
        if mapped is None:
            mapped = with_mapped_children
        return mapped

    def separate_tags(
        self,
    ) -> typing.Tuple["ArrowWeaveList", dict[PathType, "ArrowWeaveList"]]:
        tag_columns: dict[PathType, ArrowWeaveList] = {}

        def _remove_tags(list: ArrowWeaveList, path: PathType) -> ArrowWeaveList:
            if isinstance(list.object_type, tagged_value_type.TaggedValueType):
                # We need to remove _value components in the case that we are inside
                # tagged value here.
                tag_columns[path] = ArrowWeaveList(
                    list._arrow_data.field("_tag"), list.object_type.tag, list._artifact
                )
                return ArrowWeaveList(
                    list._arrow_data.field("_value"),
                    list.object_type.value,
                    list._artifact,
                )
            return list

        res = self.map_column(_remove_tags)

        reversed_tag_columns = {}
        for k, v in reversed(tag_columns.items()):
            reversed_tag_columns[k] = v

        return res, reversed_tag_columns

    def without_tags(self) -> "ArrowWeaveList":
        return self.separate_tags()[0]

    def separate_dictionaries(
        self,
    ) -> typing.Tuple["ArrowWeaveList", dict[PathType, "ArrowWeaveList"]]:
        dictionary_columns: dict[PathType, ArrowWeaveList] = {}

        def _remove_dictionaries(
            list: ArrowWeaveList, path: PathType
        ) -> typing.Optional[ArrowWeaveList]:
            if pa.types.is_dictionary(list._arrow_data.type):
                dictionary_columns[path] = ArrowWeaveList(
                    list._arrow_data.dictionary, list.object_type, list._artifact
                )
                return ArrowWeaveList(
                    list._arrow_data.indices,
                    types.Int(),
                    list._artifact,
                )
            return None

        res = self.map_column(_remove_dictionaries), dictionary_columns
        return res

    def without_dictionaries(self) -> "ArrowWeaveList":
        def _remove_dictionaries(
            list: ArrowWeaveList, path: PathType
        ) -> typing.Optional[ArrowWeaveList]:
            if pa.types.is_dictionary(list._arrow_data.type):
                return ArrowWeaveList(
                    list._arrow_data.dictionary_decode(),
                    list.object_type,
                    list._artifact,
                )
            return None

        return self.map_column(_remove_dictionaries)

    def separate_awls(
        self,
    ) -> typing.Tuple["ArrowWeaveList", dict[PathType, list["ArrowWeaveList"]]]:
        awl_columns: dict[PathType, list[ArrowWeaveList]] = {}

        def _remove_awls(
            list: ArrowWeaveList, path: PathType
        ) -> typing.Optional[ArrowWeaveList]:
            if isinstance(list.object_type, ArrowWeaveListType):
                awl_columns[path] = [
                    ArrowWeaveList(
                        a.values, list.object_type.object_type, list._artifact
                    )
                    for a in list._arrow_data
                ]
                return ArrowWeaveList(
                    pa.array([None] * len(list)), types.NoneType(), list._artifact
                )
            return None

        res = self.map_column(_remove_awls), awl_columns
        return res

    def function_type_paths(
        self,
    ) -> dict[PathType, types.Type]:
        function_type_paths: dict[PathType, types.Type] = {}

        def _save_obj_type_path(list: ArrowWeaveList, path: PathType) -> None:
            if isinstance(list.object_type, types.Function):
                function_type_paths[path] = list.object_type
            return None

        self.map_column(_save_obj_type_path)
        function_type_paths = reverse_dict(function_type_paths)
        return function_type_paths

    def obj_type_paths(
        self,
    ) -> dict[PathType, types.Type]:
        obj_type_paths: dict[PathType, types.Type] = {}

        def _save_obj_type_path(list: ArrowWeaveList, path: PathType) -> None:
            if isinstance(list.object_type, types.ObjectType):
                obj_type_paths[path] = list.object_type
            return None

        self.map_column(_save_obj_type_path)
        obj_type_paths = reverse_dict(obj_type_paths)
        return obj_type_paths

    def custom_type_paths(
        self,
    ) -> dict[PathType, types.Type]:
        custom_type_paths: dict[PathType, types.Type] = {}

        def _save_custom_type_path(list: ArrowWeaveList, path: PathType) -> None:
            if isinstance(
                list.object_type,
                # TODO: don't hardcode
                (
                    ArrowWeaveListType,
                    types.List,
                    types.Const,
                    types.Number,
                    types.Int,
                    types.Float,
                    types.Boolean,
                    types.String,
                    types.Timestamp,
                    types.NoneType,
                    wbmedia.LegacyTableNDArrayType,
                    tagged_value_type.TaggedValueType,
                    types.TypedDict,
                    types.ObjectType,
                    types.UnionType,
                    types.Function,
                ),
            ):
                return None
            custom_type_paths[path] = list.object_type

        self.map_column(_save_custom_type_path)
        return custom_type_paths

    def with_unions_as_structs(self) -> "ArrowWeaveList":
        def _replace_union_with_struct(
            col: ArrowWeaveList, path: PathType
        ) -> typing.Optional[ArrowWeaveList]:
            if isinstance(col.object_type, types.UnionType):
                non_none_members = [
                    m
                    for m in col.object_type.members
                    if not isinstance(m, types.NoneType)
                ]
                if len(non_none_members) == 1:
                    # Don't need to convert simple nullable
                    return None
                nullable = len(non_none_members) < len(col.object_type.members)
                arrs = [col._arrow_data.field(i) for i in range(len(non_none_members))]
                names = [f"_union_{i}" for i in range(len(non_none_members))]
                property_types = {n: t for n, t in zip(names, non_none_members)}
                new_type: types.Type = types.TypedDict(property_types)
                if nullable:
                    new_type = types.optional(new_type)
                return ArrowWeaveList(
                    pa.StructArray.from_arrays(arrs, names=names),
                    new_type,
                    self._artifact,
                )
            return None

        return self.map_column(_replace_union_with_struct)

    def _arrow_data_asarray_no_tags(self) -> pa.Array:
        # Remove both tags and dictionaries. You should typically leave
        # dictionaries as late as possible! So only use this if you're sure
        # you don't want them.
        no_tags = self.without_tags()
        no_dicts = no_tags.without_dictionaries()
        return no_dicts._arrow_data

    def __array__(self, dtype=None):
        # TODO: replace with to_pylist_tagged once refs are supported
        pylist = self.to_pylist_raw()
        return np.asarray(pylist)

    def __iter__(self):
        pylist = self.to_pylist_tagged()
        for x in pylist:
            yield x

    def __repr__(self):
        return f"<ArrowWeaveList: {self.object_type}>"

    def to_pylist_raw(self):
        """Used for testing, preserves _tag and _value fields"""
        return self._to_pylist_dictsafe()

    def _to_pylist_dictsafe(self):
        value_awl, dict_columns = self.separate_dictionaries()
        value_py = value_awl._arrow_data.to_pylist()

        dict_columns = {p: c._arrow_data.to_pylist() for p, c in dict_columns.items()}

        # Dictionary decode the value
        if dict_columns:
            for path, dict_col in dict_columns.items():
                path = tuple(
                    p
                    if not isinstance(p, PathItemObjectField)
                    else PathItemStructField(p.attr)
                    for p in path
                )
                set_path(
                    value_py,
                    value_awl._arrow_data,
                    (PathItemOuterList(),) + path,
                    lambda v, j: None if v == None else dict_col[v],
                )

        return value_py

    def to_pylist_notags(self):
        """Convert the ArrowWeaveList to a python list, stripping tags"""
        value_awl, _ = self.separate_tags()
        return value_awl._to_pylist_dictsafe()

    def to_pylist_tagged(self):
        """Convert the ArrowWeaveList to a python list, tagging objects correctly"""
        value, awl_columns = self.separate_awls()

        custom_type_paths = value.custom_type_paths()
        function_type_paths = value.function_type_paths()
        obj_type_paths = value.obj_type_paths()

        value_awl, dict_columns = value.separate_dictionaries()
        value_py = value_awl._arrow_data.to_pylist()

        dict_columns = {p: c._arrow_data.to_pylist() for p, c in dict_columns.items()}

        for path, obj_type in obj_type_paths.items():
            set_path(
                value_py,
                value_awl._arrow_data,
                (PathItemOuterList(),) + path,
                lambda v, j: None if v is None else obj_type.instance_class(**v),
            )
        # Dictionary decode the value, and add the tags to the tag store,
        # in a single pass.
        for path2, dict_col in dict_columns.items():
            set_path(
                value_py,
                value_awl._arrow_data,
                (PathItemOuterList(),) + path2,
                lambda v, j: None if v == None else dict_col[v],
            )

        for path, type_ in custom_type_paths.items():

            def custom_type_value(v, j):
                if v == None:
                    return None
                if isinstance(v, dict):
                    return type_.instance_from_dict(v)
                # else its a ref string
                # TODO: this does not use self.artifact, can we just drop it?
                # Do we need the type so we can load here? No...
                if ":" in v:
                    ref = ref_base.Ref.from_str(v)
                    # Note: we are forcing type here, because we already know it
                    # We don't save the types for every file in a remote artifact!
                    # But you can still reference them, because you have to get that
                    # file through an op, and therefore we know the type?
                    ref._type = type_
                    return ref.get()

                return self._artifact.get(v, type_)

            set_path(
                value_py,
                value_awl._arrow_data,
                (PathItemOuterList(),) + path,
                custom_type_value,
            )

        for path, function_type in function_type_paths.items():
            set_path(
                value_py,
                value_awl._arrow_data,
                (PathItemOuterList(),) + path,
                lambda v, j: node_ref.ref_to_node(ref_base.Ref.from_str(v)),
            )

        for path, awls in awl_columns.items():
            set_path(
                value_py,
                value_awl._arrow_data,
                (PathItemOuterList(),) + path,
                lambda v, j: awls[j],
            )
        return concrete_to_tagstore(value_py)

    def _count(self):
        return len(self._arrow_data)

    def __len__(self):
        return self._count()

    def replace_column(
        self,
        name: typing.Union[str, PathType],
        fn: typing.Callable[["ArrowWeaveList"], "ArrowWeaveList"],
    ):
        replaced = {"v": False}

        def _do_replace(
            list: ArrowWeaveList, path: PathType
        ) -> typing.Optional[ArrowWeaveList]:
            if (
                isinstance(name, tuple)
                and path == name
                or len(path) == 1
                and path[0] == name
            ):
                replaced["v"] = True
                return fn(list)
            return None

        res = self.map_column(_do_replace)
        if not replaced["v"]:
            raise ValueError("Column {} not found".format(name))
        return res

    def dictionary_encode(self) -> "ArrowWeaveList":
        return ArrowWeaveList(
            self._arrow_data.dictionary_encode(), self.object_type, self._artifact
        )

    def _index(self, index: typing.Optional[int]):
        if index == None:
            return None
        index = typing.cast(int, index)
        if len(self._arrow_data) <= index:
            return None
        # Create a temp AWL so we can leverage the `to_pylist_tagged` helper,
        # but it will only apply to a single element instead of wasting a bunch
        # of cycles. Note: this was previously memoized on the object but that
        # is not safe! You cannot save the results of `to_pylist_tagged` since
        # it is only valid in the tagging context which it was first called!
        temp_awl: ArrowWeaveList = ArrowWeaveList(
            self._arrow_data.take([index]), self.object_type, self._artifact
        )
        return temp_awl.to_pylist_tagged()[0]

    def __getitem__(self, index: int):
        return self._index(index)

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
        if self._arrow_data.type == desired_type_pyarrow_type:
            result = self
        elif (
            pa.types.is_list(self._arrow_data.type)
            and self._arrow_data.type.value_type == pa.null()
        ):
            # In this case we have a AWL<list<null>>. In these cases we run into a bunch of issues because
            # the current type is unknown. Instead, we basically just cast the AWL to the desired type.
            return ArrowWeaveList(
                self._arrow_data.cast(desired_type_pyarrow_type),
                desired_type,
                self._artifact,
            )
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
                mask=pa.compute.is_null(self._arrow_data),
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
                    pa.StructArray.from_arrays(
                        arrays=arrays,
                        names=field_names,
                        mask=pa.compute.is_null(self._arrow_data),
                    ),
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
            offsets = offsets_starting_at_zero(self._arrow_data)
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
                    mask=pa.compute.is_null(self._arrow_data),
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

                        def member_mapper_type():
                            return mappers_arrow.map_to_arrow(
                                member, self._artifact
                            ).result_type()

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
                                if pa.types.is_null(selection.type):
                                    selection = selection.cast(member_mapper_type())
                                data_arrays.append(selection)
                                break
                        else:
                            # Here we have not found the corresponding type in the current array.
                            # We will create an array of nulls.
                            data_arrays.append(
                                pa.nulls(len(self), type=member_mapper_type())
                            )

                    # Finally, combine the M arrays into a single union array.
                    field_names = [
                        desired_type_pyarrow_type.field(i).name
                        for i in range(desired_type_pyarrow_type.num_fields)
                    ]
                    result = ArrowWeaveList(
                        pa.UnionArray.from_dense(
                            type_code_array,
                            offsets,
                            data_arrays,
                            field_names,
                        ),
                        desired_type,
                        self._artifact,
                    )
                else:
                    result = ArrowWeaveList(
                        self._arrow_data,
                        types.non_none(desired_type),
                        self._artifact,
                    ).with_object_type(non_nullable_types[0])
        elif current_type == desired_type:
            # Put this at the end to support custom types
            result = self
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

            new_object_type = types.unknown_coalesce(
                types.merge_types(*new_object_types_with_pushed_down_tags)
            )

            new_arrow_arrays = [
                a.with_object_type(new_object_type)._arrow_data for a in (self, other)
            ]
            return ArrowWeaveList(
                safe_pa_concat_arrays(new_arrow_arrays), new_object_type, self._artifact
            )

    def _limit(self, limit: int):
        return ArrowWeaveList(
            self._arrow_data.slice(0, limit), self.object_type, self._artifact
        )


ArrowWeaveListType.instance_classes = ArrowWeaveList


ArrowWeaveListType.instance_classes = ArrowWeaveList
ArrowWeaveListType.instance_class = ArrowWeaveList


def dataframe_to_arrow(df):
    return ArrowWeaveList(pa.Table.from_pandas(df))
