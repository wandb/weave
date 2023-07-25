import dataclasses
import typing
import pyarrow as pa
from . import errors


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
