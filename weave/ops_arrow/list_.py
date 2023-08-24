import typing
import contextvars
import contextlib
import inspect
import typing_extensions
import dataclasses
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import textwrap

from .. import ref_base
from .. import weave_types as types
from .. import box
from .. import weave_internal
from ..ops_primitives import _dict_utils
from .. import errors
from .. import graph
from ..language_features.tagging import (
    tagged_value_type,
)
from .. import artifact_base
from .. import node_ref
from ..language_features.tagging import tag_store

from .arrow import (
    safe_is_null,
    ArrowWeaveListType,
    offsets_starting_at_zero,
    pretty_print_arrow_type,
    arrow_zip,
    arrow_as_array,
)
from .. import debug_types


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


def diff_arrow_type(t1, t2):
    if t1 == t2:
        return None
    if (
        isinstance(t1, pa.StructType)
        and isinstance(t2, pa.StructType)
        or isinstance(t1, pa.UnionType)
        and isinstance(t2, pa.UnionType)
    ):
        if isinstance(t1, pa.StructType):
            error_prefix = "structs"
        else:
            error_prefix = "unions"
        if t1.num_fields != t2.num_fields:
            return f"{error_prefix} different number of fields"
        for f1, f2 in zip(t1, t2):
            if f1.name != f2.name:
                return f"{error_prefix} different field names: {f1.name} != {f2.name}"
            diff = diff_arrow_type(f1.type, f2.type)
            if diff is not None:
                return f"{error_prefix} field {f1.name}: {diff}"
        return None
    if isinstance(t1, pa.ListType) and isinstance(t2, pa.ListType):
        return diff_arrow_type(t1.value_type, t2.value_type)
    return f"{t1}\n!=\n{t2}"


def first_non_none(v):
    for i in v:
        if i is not None:
            return i
    return None


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
            # print("V", v)
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


def weave_arrow_type_check(
    wt: types.Type, arr: pa.Array, optional: bool = False
) -> typing.Optional[str]:
    reasons: list[str] = []
    at: pa.DataType = arr.type
    if wt == types.Any():
        reasons.append("Any not allowed")
    elif isinstance(wt, types.UnionType):
        for i in range(len(wt.members)):
            for j in range(i + 1, len(wt.members)):
                if not isinstance(
                    types.merge_types(wt.members[i], wt.members[j]), types.UnionType
                ):
                    reasons.append(f"Union members {i} and {j} are mergable")
        non_none_members = [m for m in wt.members if m != types.NoneType()]
        none_member_count = len(wt.members) - len(non_none_members)
        if none_member_count > 1:
            reasons.append("Multiple None members in Union")
        elif none_member_count == 1:
            # Nullable case
            # TODO: Actually must check nullable!
            reason = None
            if len(non_none_members) == 0:
                reason = "NoneType not allowed in Union with no other members"
            if at != pa.null():
                if len(non_none_members) == 1:
                    reason = weave_arrow_type_check(
                        non_none_members[0], arr, optional=True
                    )
                else:
                    reason = weave_arrow_type_check(
                        types.UnionType(*non_none_members), arr, optional=True
                    )
            if reason is not None:
                reasons.append(f"Nullable member: {reason}")
        else:
            if not pa.types.is_union(at):
                reasons.append(f"Expected UnionType, got {at}")
            else:
                if len(wt.members) != len(at):
                    reasons.append(
                        f"Union length mismatch: {len(wt.members)} != {len(at)}"
                    )
                else:
                    for i, w in enumerate(wt.members):
                        reason = weave_arrow_type_check(
                            w, arr.field(i), optional=optional
                        )
                        if reason is not None:
                            reasons.append(f"Union member {i}: {reason}")
    elif optional and pa.types.is_null(at):
        pass
    else:
        # Nullable check. This surfaces a ton of failures...
        # if wt != types.NoneType() and not optional and arr.null_count > 0:
        #     reasons.append("Non-nullable but array has nulls")

        if isinstance(wt, tagged_value_type.TaggedValueType):
            tag_reason = weave_arrow_type_check(
                wt.tag, arr.field("_tag"), optional=optional
            )
            if tag_reason is not None:
                reasons.append(f"TaggedValue tag: {tag_reason}")
            value_reason = weave_arrow_type_check(
                wt.value, arr.field("_value"), optional=optional
            )
            if value_reason is not None:
                reasons.append(f"TaggedValue value: {value_reason}")

        elif isinstance(wt, types.Const):
            reasons.append("Const not allowed")

        elif isinstance(wt, types.Function):
            if not pa.types.is_string(at):
                reasons.append(f"Expected StringType, got {at}")

        elif isinstance(wt, types.TypedDict):
            if not pa.types.is_struct(at):
                reasons.append(f"Expected StructType, got {at}")
            else:
                at_fields_by_name = {f.name: f for f in at}
                for k, v in wt.property_types.items():
                    if k not in at_fields_by_name:
                        reasons.append(f"Missing field {k}")
                    else:
                        reason = weave_arrow_type_check(
                            v, arr.field(k), optional=optional
                        )
                        if reason is not None:
                            reasons.append(f"Field {k}: {reason}")

        elif isinstance(wt, (types.List, ArrowWeaveListType)):
            if not pa.types.is_list(at):
                reasons.append(f"Expected ListType, got {at}")
            else:
                reason = weave_arrow_type_check(
                    wt.object_type, arr.flatten(), optional=optional
                )
                if reason is not None:
                    reasons.append(f"List element: {reason}")

        elif isinstance(wt, types.ObjectType):
            if not pa.types.is_struct(at):
                reasons.append(f"Expected StructType, got {at}")
            else:
                at_fields_by_name = {f.name: f for f in at}
                for k, v in wt.property_types().items():
                    if k not in at_fields_by_name:
                        reasons.append(f"Missing field {k}")
                    else:
                        reason = weave_arrow_type_check(
                            v, arr.field(k), optional=optional
                        )
                        if reason is not None:
                            reasons.append(f"Field {k}: {reason}")
        elif isinstance(wt, types.String):
            if pa.types.is_dictionary(at):
                if not pa.types.is_string(at.value_type):
                    reasons.append(
                        f"Expected StringType as dictionary type, got {at.value_type}"
                    )
            elif not pa.types.is_string(at):
                reasons.append(f"Expected StringType, got {at}")
        elif isinstance(wt, types.UnknownType):
            if len(arr) != 0:
                reasons.append("Non-zero length array with UnknownType")
        elif isinstance(wt, types.Int):
            # We allow float32/64 because of a bug in our unnest implementation
            # which relies on pandas. TODO: Remove this when we fix unnest.
            if (
                not pa.types.is_float64(at)
                and not pa.types.is_int64(at)
                and not pa.types.is_float32(at)
                and not pa.types.is_int32(at)
            ):
                reasons.append(
                    f"Expected int64 or int32 (float32/64 allowed because of unnest bug), got {at}"
                )
        elif isinstance(wt, types.Float):
            if not pa.types.is_float64(at) and not pa.types.is_float32(at):
                reasons.append(f"Expected float64 or float32, got {at}")
        elif isinstance(wt, types.Number):
            if (
                not pa.types.is_float64(at)
                and not pa.types.is_int64(at)
                and not pa.types.is_float32(at)
                and not pa.types.is_int32(at)
            ):
                reasons.append(
                    f"Expected float64 or float32 or int64 or int32, got {at}"
                )
        elif isinstance(wt, types.Boolean):
            if not pa.types.is_boolean(at):
                reasons.append(f"Expected boolean, got {at}")
        elif isinstance(wt, types.NoneType):
            # We don't check for pa.types.is_null(at) because we can have for
            # example at == int32 with all nulls.
            if not arr.null_count == len(arr):
                reasons.append(f"Expected all nulls, got {arr.null_count}")
        elif isinstance(wt, types.Timestamp):
            if not pa.types.is_timestamp(at):
                reasons.append(f"Expected TimestampType, got {at}")
        elif types.is_custom_type(wt):
            if pa.types.is_dictionary(at):
                if not pa.types.is_string(at.value_type):
                    reasons.append(
                        f"Expected StringType as dictionary type, got {at.value_type}"
                    )
            elif not pa.types.is_string(at):
                reasons.append(f"Expected StringType, got {at}")
        else:
            reasons.append(f"Unhandled case: {wt}, {at}")

    if reasons:
        indented_reasons = textwrap.indent("\n".join(reasons), "  ")
        print("TYPE", type(wt))
        return f"{debug_types.short_type(wt)}, {str(at)[:50]}\n{indented_reasons}"

    return None


_awl_invalid_reason: contextvars.ContextVar[
    typing.Optional[str]
] = contextvars.ContextVar("_awl_invalid_reason", default=None)


@contextlib.contextmanager
def unsafe_awl_construction(reason: str):
    token = None
    if _awl_invalid_reason.get() is None:
        token = _awl_invalid_reason.set(reason)
    try:
        yield
    finally:
        if token is not None:
            _awl_invalid_reason.reset(token)


ArrowWeaveListObjectTypeVar = typing.TypeVar("ArrowWeaveListObjectTypeVar")


class ArrowWeaveList(typing.Generic[ArrowWeaveListObjectTypeVar]):
    _arrow_data: pa.Array
    object_type: types.Type

    # TODO: Refactor to disable None artifact? (Only used in tests)
    def __init__(
        self,
        arrow_data: typing.Union[pa.Table, pa.ChunkedArray, pa.Array],
        object_type=None,
        artifact: typing.Optional[artifact_base.Artifact] = None,
        invalid_reason=None,
    ) -> None:
        # Do not dictionary decode this array! That will break performance.
        # Note we combine chunks here, to make the internal interface easy
        # to use. In the future we could refactor to retain chunked form.
        if isinstance(arrow_data, pa.Array):
            self._arrow_data = arrow_data
        elif isinstance(arrow_data, pa.Table):
            self._arrow_data = pa.StructArray.from_arrays(
                # TODO: we shouldn't need to combine chunks, we can produce this in the
                # original chunked form for zero copy
                [c.combine_chunks() for c in arrow_data.columns],
                names=arrow_data.column_names,
            )
        elif isinstance(arrow_data, pa.ChunkedArray):
            self._arrow_data = arrow_data.combine_chunks()
        else:
            raise TypeError(
                "Expected pyarrow Array, ChunkdArray or Table, got %s"
                % type(arrow_data)
            )

        self.object_type = object_type
        if self.object_type is None:
            self.object_type = types.TypeRegistry.type_of(self._arrow_data).object_type
        self._artifact = artifact
        if invalid_reason is None:
            invalid_reason = _awl_invalid_reason.get()
        self._invalid_reason = invalid_reason

        self._validate()

    def _validate(self) -> None:
        if self._invalid_reason is None:
            self._validate_weave_type()
        self._validate_arrow_data()

    def _validate_weave_type(self) -> None:
        return

        # Validation disabled
        arr = self._arrow_data
        type_match_summary = weave_arrow_type_check(self.object_type, arr)
        if type_match_summary != None:
            print()
            print("ArrowWeaveList VALIDATION ERROR")
            print()
            print("ArrowWeaveList.object_type", self.object_type)
            print()
            print(
                "ArrowWeaveList._arrow_data.type\n",
                pretty_print_arrow_type(self._arrow_data.type),
            )
            print()
            print(type_match_summary)
            raise ValueError(f"ArrowWeaveList validation err: {type_match_summary}")

    def _validate_arrow_data(self) -> None:
        return

        # Validation disabled: this seems to usually be fast, but can take
        # many seconds for certain arrays.
        try:
            self._arrow_data.validate(full=True)
        except pa.ArrowInvalid:
            raise

    def validate(self) -> None:
        self._validate_weave_type()
        self._validate_arrow_data()
        self._invalid_reason = None

    def with_column(self, key: str, val: "ArrowWeaveList"):
        """Add a column to the AWL.

        key can be a dot-separated path. Any non-TypedDict values encountered
        in traversal will be replaced with empty TypedDicts.

        leaf will be replaced with val if leaf exists. Added value is always
        added to the end of the TypedDict (remember, they are ordered).

        Result len is always len(self). Will raise if len(val) != len(self)
        """
        if not isinstance(self.object_type, types.TypedDict):
            self = make_vec_dict()
        self_object_type = typing.cast(types.TypedDict, self.object_type)

        path = _dict_utils.split_escaped_string(key)

        if len(path) > 1:
            return self.with_column(
                path[0], self.column(path[0]).with_column(".".join(path[1:]), val)
            )

        col_names = list(self_object_type.property_types.keys())
        col_data = [self._arrow_data.field(i) for i in range(len(col_names))]
        property_types = {**self_object_type.property_types}
        try:
            key_index = col_names.index(key)
        except ValueError:
            key_index = None
        if key_index is not None:
            property_types.pop(key)
            col_names.pop(key_index)
            col_data.pop(key_index)
        col_names.append(key)
        col_data.append(val._arrow_data)
        property_types[key] = val.object_type
        return ArrowWeaveList(
            pa.StructArray.from_arrays(col_data, names=col_names),
            types.TypedDict(property_types),
            self._artifact,
        )

    def with_columns(self, cols: dict[str, "ArrowWeaveList"]):
        for k, v in cols.items():
            self = self.with_column(k, v)
        return self

    def map_column(
        self,
        fn: typing.Callable[
            ["ArrowWeaveList", PathType], typing.Optional["ArrowWeaveList"]
        ],
        pre_fn: typing.Optional[
            typing.Callable[
                ["ArrowWeaveList", PathType], typing.Optional["ArrowWeaveList"]
            ]
        ] = None,
    ) -> "ArrowWeaveList":
        return self._map_column(fn, pre_fn, ())

    def _map_column(
        self,
        fn: typing.Callable[
            ["ArrowWeaveList", PathType], typing.Optional["ArrowWeaveList"]
        ],
        pre_fn: typing.Optional[
            typing.Callable[
                ["ArrowWeaveList", PathType], typing.Optional["ArrowWeaveList"]
            ]
        ],
        path: PathType,
    ) -> "ArrowWeaveList":
        if pre_fn is not None:
            pre_mapped = pre_fn(self, path)
            if pre_mapped is not None:
                self = pre_mapped
        with_mapped_children = self
        if isinstance(self.object_type, types.UnknownType):
            # Only occurs in empty list. Don't map into this.
            return self
        if isinstance(self.object_type, types.Const):
            with_mapped_children = ArrowWeaveList(
                self._arrow_data, self.object_type.val_type, self._artifact
            )._map_column(fn, pre_fn, path)
        if self._arrow_data.type == pa.null():
            # we can have a null array at any type. We stop
            # mapping when we hit one. The caller should specifically handle
            # null arrays in pre or post map functions
            pass
        elif isinstance(self.object_type, types.TypedDict):
            arr = self._arrow_data
            properties: dict[str, ArrowWeaveList] = {
                k: ArrowWeaveList(arr.field(k), v, self._artifact)._map_column(
                    fn, pre_fn, path + (PathItemStructField(k),)
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

            # set invalid_reason to the first non-None invalid reason found in
            # properties
            invalid_reason = first_non_none(
                v._invalid_reason for v in properties.values()
            )

            with_mapped_children = ArrowWeaveList(
                result_arr,
                types.TypedDict({k: v.object_type for k, v in properties.items()}),
                self._artifact,
                invalid_reason=invalid_reason,
            )
        elif isinstance(self.object_type, types.ObjectType):
            arr = self._arrow_data
            attrs: dict[str, ArrowWeaveList] = {
                k: ArrowWeaveList(arr.field(k), v, self._artifact)._map_column(
                    fn, pre_fn, path + (PathItemObjectField(k),)
                )
                for k, v in self.object_type.property_types().items()
            }

            # Types of some of the attrs may have changed. But some property types on object
            # types are no variable, and it is invalid to change them from our type system's
            # perspective. So the result here is invalid ArrowWeaveList. The results should
            # only be used in cirumstances where this is acceptable.
            with_mapped_children = ArrowWeaveList(
                pa.StructArray.from_arrays(
                    [v._arrow_data for v in attrs.values()],
                    list(attrs.keys()),
                    mask=pa.compute.is_null(arr),
                ),
                self.object_type,
                self._artifact,
                invalid_reason="mapped_column on ObjectType can produce invalid ArrowWeaveList",
            )
        elif isinstance(self.object_type, (types.List, ArrowWeaveListType)):
            arr = self._arrow_data
            items: ArrowWeaveList = ArrowWeaveList(
                arr.flatten(), self.object_type.object_type, self._artifact
            )._map_column(fn, pre_fn, path + (PathItemList(),))
            # print("SELF OBJECT TYPE", self.object_type)
            # print("SELF ARROW DATA TYPE", self._arrow_data.type)
            with_mapped_children = ArrowWeaveList(
                pa.ListArray.from_arrays(
                    offsets_starting_at_zero(self._arrow_data),
                    items._arrow_data,
                    mask=pa.compute.is_null(arr),
                ),
                self.object_type.__class__(items.object_type),
                self._artifact,
                invalid_reason=items._invalid_reason,
            )
        elif isinstance(self.object_type, tagged_value_type.TaggedValueType):
            arr = self._arrow_data
            tag: ArrowWeaveList = ArrowWeaveList(
                self._arrow_data.field("_tag"), self.object_type.tag, self._artifact
            )._map_column(fn, pre_fn, path + (PathItemTaggedValueTag(),))
            value: ArrowWeaveList = ArrowWeaveList(
                self._arrow_data.field("_value"), self.object_type.value, self._artifact
            )._map_column(fn, pre_fn, path + (PathItemTaggedValueValue(),))
            with_mapped_children = ArrowWeaveList(
                pa.StructArray.from_arrays(
                    [tag._arrow_data, value._arrow_data],
                    ["_tag", "_value"],
                    mask=pa.compute.is_null(arr),
                ),
                tagged_value_type.TaggedValueType(tag.object_type, value.object_type),  # type: ignore
                self._artifact,
                invalid_reason=tag._invalid_reason or value._invalid_reason,
            )
        elif isinstance(self.object_type, types.UnionType):
            non_none_members = [
                m for m in self.object_type.members if not isinstance(m, types.NoneType)
            ]
            nullable = len(non_none_members) < len(self.object_type.members)
            if len(non_none_members) == 1:
                non_none_member = ArrowWeaveList(
                    self._arrow_data,
                    non_none_members[0],
                    self._artifact,
                )._map_column(fn, pre_fn, path)
                with_mapped_children = ArrowWeaveList(
                    non_none_member._arrow_data,
                    types.optional(non_none_member.object_type),
                    self._artifact,
                    invalid_reason=non_none_member._invalid_reason,
                )
            elif len(non_none_members) > 1:
                arr = self._arrow_data
                members: list[typing.Optional[ArrowWeaveList]] = [
                    ArrowWeaveList(
                        arr.field(i),
                        types.optional(member_type) if nullable else member_type,
                        self._artifact,
                    )._map_column(fn, pre_fn, path + (PathItemUnionEntry(i),))
                    for i, member_type in enumerate(non_none_members)
                ]

                # Types of some of the members may have changed. We need to maintain
                # the invariant that types within a union are not mergeable via
                # merge_types. So we walk through the new members looking for
                # mergeable types, and concatenating them, while computing
                # new type_codes and offsets arrays

                type_codes = self._arrow_data.type_codes
                offsets = self._arrow_data.offsets
                for i in range(len(members)):
                    if members[i] is None:
                        # We've already merged this member into another, so
                        # find the first non-None member to start from.
                        for j in range(i + 1, len(members)):
                            if members[j] is not None:
                                members[i] = members[j]
                                members[j] = None
                                type_codes = pc.choose(
                                    pc.equal(type_codes, j),
                                    type_codes,
                                    pa.scalar(i, pa.int8()),
                                )
                                break
                    for j in range(i + 1, len(members)):
                        member_i = members[i]
                        member_j = members[j]
                        if (
                            member_i is not None
                            and member_j is not None
                            and types.types_are_mergeable(
                                member_i.object_type, member_j.object_type
                            )
                        ):
                            merged = True
                            offsets = pc.choose(
                                pc.equal(type_codes, j),
                                offsets,
                                pc.add(offsets, len(member_i)),
                            ).cast(pa.int32())
                            type_codes = pc.choose(
                                pc.equal(type_codes, j),
                                type_codes,
                                pa.scalar(i, pa.int8()),
                            )
                            from . import concat

                            members[i] = concat.concatenate(member_i, member_j)
                            members[j] = None

                final_members: list[ArrowWeaveList] = [
                    m for m in members if m is not None
                ]
                if len(final_members) == 1:
                    with_mapped_children = ArrowWeaveList(
                        final_members[0]._arrow_data.take(offsets),
                        final_members[0].object_type,
                        final_members[0]._artifact,
                    )
                else:
                    new_type_members = [m.object_type for m in final_members]
                    if nullable:
                        new_type_members.append(types.NoneType())

                    invalid_reason = first_non_none(
                        m._invalid_reason for m in final_members
                    )
                    with_mapped_children = ArrowWeaveList(
                        pa.UnionArray.from_dense(
                            type_codes,
                            offsets,
                            [m._arrow_data for m in final_members],
                        ),
                        types.UnionType(*new_type_members),
                        # types.union(*new_type_members),
                        self._artifact,
                        invalid_reason=invalid_reason,
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
                    # Don't change the object type to Int. Instead, we mark the ArrowWeaveList
                    # as invalid (the arrow type no longer matches object_type)
                    list.object_type,
                    list._artifact,
                    invalid_reason="Dictionary removed",
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
                    invalid_reason="Dictionary removed",
                )
            return None

        return self.map_column(_remove_dictionaries)

    def separate_awls(
        self,
    ) -> typing.Tuple[
        "ArrowWeaveList", dict[PathType, list[typing.Optional["ArrowWeaveList"]]]
    ]:
        awl_columns: dict[PathType, list[typing.Optional[ArrowWeaveList]]] = {}

        def _remove_awls(
            list: ArrowWeaveList, path: PathType
        ) -> typing.Optional[ArrowWeaveList]:
            if isinstance(list.object_type, ArrowWeaveListType):
                awl_columns[path] = [
                    ArrowWeaveList(
                        a.values, list.object_type.object_type, list._artifact
                    )
                    if a.values is not None
                    else None
                    for a in list._arrow_data
                ]
                return ArrowWeaveList(
                    pa.array([None] * len(list)), types.NoneType(), list._artifact
                )
            return None

        # Use pre-order traversal. We only want the top most awls.
        return self.map_column(lambda x, y: None, _remove_awls), awl_columns

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
            # print("OBJ TYPE PATH", path)
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

    def _index(
        self,
        index: typing.Optional[typing.Union[int, typing.List[typing.Optional[int]]]],
    ):
        if index == None:
            return None
        indexes: pa.Array
        if isinstance(index, int):
            indexes = [index]
        elif isinstance(index, ArrowWeaveList):
            indexes = index._arrow_data
        else:
            indexes = index

        arr = self._arrow_data
        length = len(arr)
        neg_cond = pc.less(indexes, 0)
        indexes_neg = pc.add(indexes, length)
        indexes = pc.choose(neg_cond, indexes, indexes_neg)
        out_of_bounds = pc.or_(pc.less(indexes, 0), pc.greater_equal(indexes, length))
        indexes_bounds_checked = pc.choose(
            out_of_bounds, indexes, pa.scalar(None, pa.int64())
        )
        result_rows = pc.take(arr, indexes_bounds_checked)
        awl: ArrowWeaveList = ArrowWeaveList(
            result_rows, self.object_type, self._artifact
        )
        if isinstance(index, int):
            return awl.to_pylist_tagged()[0]
        return awl

    def __getitem__(
        self,
        index: typing.Optional[typing.Union[int, typing.List[typing.Optional[int]]]],
    ):
        return self._index(index)

    def _slice(self, start: int, stop: int):
        # We don't slice, we take to get a copy. Arrow slicing is confusing.
        # I was seeing that type_codes in sliced unions were offset somehow...
        return ArrowWeaveList(
            self._arrow_data.take(np.arange(start, stop)),
            self.object_type,
            self._artifact,
        )

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
            new_data = arrow_obj.append_column(name, [data])
        else:
            raise ValueError(
                f"Cannot append column to {type(self._arrow_data)} object."
            )

        return ArrowWeaveList(new_data, None, self._artifact)

    def keys(self) -> list[str]:
        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            value_type = self.object_type.value
            if isinstance(value_type, types.TypedDict):
                return list(value_type.property_types.keys())
        elif isinstance(self.object_type, types.TypedDict):
            return list(self.object_type.property_types.keys())
        raise ValueError("Cannot get keys from non-TypedDict.")

    def _split_none(self) -> typing.Tuple[bool, "ArrowWeaveList"]:
        if isinstance(self.object_type, types.UnionType):
            optional, non_none_type = types.split_none(self.object_type)
            return optional, ArrowWeaveList(
                self._arrow_data,
                non_none_type,
                self._artifact,
                invalid_reason="maybe optional",
            )
        return False, self

    def _as_optional(self) -> "ArrowWeaveList":
        invalid_reason = self._invalid_reason
        if self._invalid_reason == "maybe optional":
            invalid_reason = None
        return ArrowWeaveList(
            self._arrow_data,
            types.optional(self.object_type),
            self._artifact,
            invalid_reason=invalid_reason,
        )

    def _null_mask(self) -> pa.Array:
        return safe_is_null(self._arrow_data)

    def column(self, name: str) -> "ArrowWeaveList":
        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            return make_vec_taggedvalue(
                self.tagged_value_tag(),
                self.tagged_value_value().column(name),
                is_null_mask=self._null_mask(),
            )
        elif isinstance(self.object_type, types.UnionType):
            optional, non_none = self._split_none()
            if optional and not isinstance(non_none.object_type, types.UnionType):
                return non_none.column(name)._as_optional()
            raise ValueError(
                f"Cannot get column {name} from non-TypedDict or ObjectType."
            )
        elif isinstance(self.object_type, types.TypedDict):
            property_types = self.object_type.property_types
        elif isinstance(self.object_type, types.ObjectType):
            property_types = self.object_type.property_types()
        else:
            raise ValueError(
                f"Cannot get column {name} from non-TypedDict or ObjectType."
            )

        if name not in property_types:
            return make_vec_none(len(self))

        return ArrowWeaveList(
            self._arrow_data.field(name),
            property_types[name],
            self._artifact,
            invalid_reason=self._invalid_reason,
        )

    def unique(self) -> "ArrowWeaveList":
        return ArrowWeaveList(
            pa.compute.unique(self._arrow_data),
            types.split_none(self.object_type)[1],
            self._artifact,
        )

    def tagged_value_tag(self) -> "ArrowWeaveListGeneric[types.TypedDict]":
        if not isinstance(self.object_type, tagged_value_type.TaggedValueType):
            raise ValueError("Cannot get tagged_value_tag from non-TaggedValueType")

        return ArrowWeaveListGeneric[types.TypedDict](
            self._arrow_data.field("_tag"), self.object_type.tag, self._artifact
        )

    def tagged_value_value(self) -> "ArrowWeaveList":
        if not isinstance(self.object_type, tagged_value_type.TaggedValueType):
            raise ValueError("Cannot get tagged_value_tag from non-TaggedValueType")

        return ArrowWeaveList(
            self._arrow_data.field("_value"), self.object_type.value, self._artifact
        )

    def untagged(self) -> "ArrowWeaveList":
        if isinstance(self.object_type, tagged_value_type.TaggedValueType):
            return self.tagged_value_value()
        return self

    def _make_lambda_node(
        self, fn: typing.Union[typing.Callable[[typing.Any], typing.Any], graph.Node]
    ):
        if isinstance(fn, graph.Node):
            return fn

        sig = inspect.signature(fn)
        if len(sig.parameters) == 1:
            vars = {"row": self.object_type}
        elif len(sig.parameters) == 2:
            vars = {"row": self.object_type, "index": types.Int()}
        else:
            raise ValueError(
                "Functions passed to ArrowWeaveList.apply must have 1 or 2 parameters (row, [index])"
            )
        return weave_internal.define_fn(vars, fn).val

    def apply(
        self, fn: typing.Union[typing.Callable[[typing.Any], typing.Any], graph.Node]
    ):
        fn = self._make_lambda_node(fn)
        from .vectorize import _apply_fn_node_with_tag_pushdown

        return _apply_fn_node_with_tag_pushdown(self, fn)  # type: ignore

    def concat(self, other: "ArrowWeaveList") -> "ArrowWeaveList":
        from . import concat

        return concat.concatenate(self, other)

    def join2(
        self: "ArrowWeaveList",
        other: "ArrowWeaveList",
        join1Fn: graph.OutputNode,
        join2Fn: graph.OutputNode,
        alias1: typing.Optional[str] = None,
        alias2: typing.Optional[str] = None,
        leftOuter: bool = False,
        rightOuter: bool = False,
    ):
        join1Fn = self._make_lambda_node(join1Fn)
        join2Fn = other._make_lambda_node(join2Fn)
        from . import list_join

        return list_join.join2_impl(
            self, other, join1Fn, join2Fn, alias1, alias2, leftOuter, rightOuter
        )

    def _limit(self, limit: int):
        return ArrowWeaveList(
            self._arrow_data.slice(0, limit), self.object_type, self._artifact
        )

    def _with_object_type(self, object_type: types.Type, invalid_reason=None):
        return ArrowWeaveList(
            self._arrow_data, object_type, self._artifact, invalid_reason=invalid_reason
        )

    def _clear_invalid_reason(self):
        return ArrowWeaveList(
            self._arrow_data, self.object_type, self._artifact, invalid_reason=None
        )


ArrowWeaveListGenericType = typing.TypeVar(
    "ArrowWeaveListGenericType", bound=types.Type
)


class ArrowWeaveListGeneric(
    ArrowWeaveList[typing.Any], typing.Generic[ArrowWeaveListGenericType]
):
    object_type: ArrowWeaveListGenericType


ArrowWeaveListType.instance_classes = ArrowWeaveList


ArrowWeaveListType.instance_classes = ArrowWeaveList
ArrowWeaveListType.instance_class = ArrowWeaveList


def is_typedict_arrowweavelist(
    val: ArrowWeaveList,
) -> typing_extensions.TypeGuard[ArrowWeaveListGeneric[types.TypedDict]]:
    return isinstance(val.object_type, types.TypedDict)


def is_object_arrowweavelist(
    val: ArrowWeaveList,
) -> typing_extensions.TypeGuard[ArrowWeaveListGeneric[types.ObjectType]]:
    return isinstance(val.object_type, types.ObjectType)


def is_taggedvalue_arrowweavelist(
    val: ArrowWeaveList,
) -> typing_extensions.TypeGuard[
    ArrowWeaveListGeneric[tagged_value_type.TaggedValueType]
]:
    return isinstance(val.object_type, tagged_value_type.TaggedValueType)


def is_list_arrowweavelist(
    val: ArrowWeaveList,
) -> typing_extensions.TypeGuard[ArrowWeaveListGeneric[types.List]]:
    return types.List().assign_type(val.object_type)


def dataframe_to_arrow(df):
    return ArrowWeaveList(pa.Table.from_pandas(df))


pandas_to_awl = dataframe_to_arrow


def make_vec_none(length: int) -> ArrowWeaveList:
    return ArrowWeaveList(pa.nulls(length), types.NoneType(), None)


def make_vec_dict(**kwargs: ArrowWeaveList):
    arr = pa.StructArray.from_arrays(
        [v._arrow_data for v in kwargs.values()], [k for k in kwargs.keys()]
    )
    property_types = {k: v.object_type for k, v in kwargs.items()}
    return ArrowWeaveList(arr, types.TypedDict(property_types), None)


def make_vec_taggedvalue(
    tag: ArrowWeaveListGeneric[types.TypedDict],
    value: ArrowWeaveList,
    is_null_mask: typing.Optional[pa.Array] = None,
):
    tag_types = tag.object_type.property_types
    value_type = value.object_type
    tag_data = tag._arrow_data
    value_data = value._arrow_data
    if isinstance(value_type, tagged_value_type.TaggedValueType):
        # If value is a tagged value, we flatten by merging the tags and
        # pulling the value up.
        value_type_types = value_type.tag.property_types
        new_tag_types = {**tag_types, **value_type_types}
        if len(new_tag_types) != len(tag_types) + len(value_type_types):
            raise ValueError("Tagged value types must be disjoint")
        tag_types = new_tag_types
        value_type = value_type.value

        value_tag_data = value_data.field("_tag")
        tag_data = pa.StructArray.from_arrays(
            [tag_data.field(f.name) for f in tag_data.type]
            + [value_tag_data.field(f.name) for f in value_tag_data.type],
            names=[f.name for f in tag_data.type]
            + [f.name for f in value_tag_data.type],
        )
        value_data = value_data.field("_value")
    arr = pa.StructArray.from_arrays(
        [tag_data, value_data],
        ["_tag", "_value"],
        mask=is_null_mask,
    )
    return ArrowWeaveList(
        arr, tagged_value_type.TaggedValueType(types.TypedDict(tag_types), value_type), None  # type: ignore
    )


def awl_zip(*arrs: ArrowWeaveList) -> ArrowWeaveList:
    if not arrs:
        raise ValueError("Cannot zip empty list")
    from . import convert

    arrs = convert.unify_types(*arrs)
    zipped = arrow_zip(*[a._arrow_data for a in arrs])
    return ArrowWeaveList(zipped, types.List(arrs[0].object_type), None)
