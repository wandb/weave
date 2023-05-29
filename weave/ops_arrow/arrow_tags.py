import typing
import pyarrow as pa
from pyarrow import compute as pc

from ..language_features.tagging import tag_store, process_opdef_output_type
from .. import weave_types as types

from .arrow import offsets_starting_at_zero
from . import convert

if typing.TYPE_CHECKING:
    from list_ import ArrowWeaveList  # type: ignore[import]


def recursively_encode_pyarrow_strings_as_dictionaries(array: pa.Array) -> pa.Array:
    if pa.types.is_struct(array.type):
        if array.type.num_fields == 0:
            return array
        return pa.StructArray.from_arrays(
            [
                recursively_encode_pyarrow_strings_as_dictionaries(
                    array.field(field.name)
                )
                for field in array.type
            ],
            [field.name for field in array.type],
            mask=pa.compute.invert(array.is_valid()),
        )
    elif pa.types.is_list(array.type):
        return pa.ListArray.from_arrays(
            offsets_starting_at_zero(array),
            recursively_encode_pyarrow_strings_as_dictionaries(array.flatten()),
            mask=pa.compute.invert(array.is_valid()),
        )
    elif array.type == pa.string():
        return pc.dictionary_encode(array)
    else:
        return array


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
        # Don't overwrite tags that already exist, we want to keep the innermost ones!
        if tag_field.name not in tag_names:
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


def tag_arrow_array_elements_with_single_tag_dict(
    array: pa.Array, py_tags: dict
) -> pa.StructArray:
    tag_no_dictionary = convert.to_arrow([py_tags])._arrow_data
    tag_maybe_dictionary_encoded = recursively_encode_pyarrow_strings_as_dictionaries(
        tag_no_dictionary
    )
    tags = pa.repeat(tag_maybe_dictionary_encoded[0], len(array))
    return direct_add_arrow_tags(array, tags)


def awl_add_arrow_tags(
    l: "ArrowWeaveList", arrow_tags: pa.StructArray, tag_type: types.Type
):
    data = l._arrow_data
    new_value = direct_add_arrow_tags(data, arrow_tags)
    new_object_type = process_opdef_output_type.op_make_type_tagged_resolver(
        l.object_type, tag_type
    )
    from .list_ import ArrowWeaveList

    res: ArrowWeaveList = ArrowWeaveList(new_value, new_object_type, l._artifact)
    if tag_store.is_tagged(l):
        res = tag_store.add_tags(res, tag_store.get_tags(l))
    return res


def tag_awl_list_elements_with_single_tag_dict(
    awl: "ArrowWeaveList", py_tags: dict
) -> "ArrowWeaveList":
    tag_type = types.TypeRegistry.type_of(py_tags)
    tag_array = tag_arrow_array_elements_with_single_tag_dict(
        awl._arrow_data, py_tags
    ).field("_tag")
    return awl_add_arrow_tags(awl, tag_array, tag_type)


def pushdown_list_tags(arr: "ArrowWeaveList") -> "ArrowWeaveList":
    if tag_store.is_tagged(arr):
        tag = tag_store.get_tags(arr)
        arr = tag_awl_list_elements_with_single_tag_dict(arr, tag)
    return arr
